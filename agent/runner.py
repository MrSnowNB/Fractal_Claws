#!/usr/bin/env python3
"""
runner.py — Fractal Claws agent skeleton v7

Single entry point. Reads all config from settings.yaml.
No model names, no depths, no tiers hardcoded here.

Usage:
    python agent/runner.py                        # drain all open tickets
    python agent/runner.py --goal "<goal>"        # decompose goal then drain
    python agent/runner.py --once                 # dispatch one ticket then exit
    python agent/runner.py --no-prewarm           # skip model pre-warm (fast start)
    python agent/runner.py --ticket TASK-005      # run a specific ticket by ID
    python agent/runner.py --dry-run              # print next ticket, do not execute

v7 changes (optimize-fractal-claws):
    - Imports consolidated: src.tools.registry + src.tools.terminal (canonical)
    - Scratch file system: per-ticket REASONING/VERIFY audit trail (ported from MUMPS_Bot)
    - In-progress state: tickets move open → in_progress → closed/failed
    - Gate command support: subprocess acceptance testing per ticket
    - Failure handling: _handle_failure() writes to ISSUE.md
    - Session lifecycle: SESSION_START/SESSION_END in journal
    - Retry loop: proper attempt tracking with move-back-to-open
    - call_model retry fix: exactly MAX_RETRIES+1 attempts
    - write_skill() fix: proper dict argument
"""

import os
import re
import sys
import glob
import time
import uuid
import yaml
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from openai import OpenAI

# Add project root to sys.path for imports to work from any invocation directory
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# BUG 1+11 FIX: Import from canonical src/tools/ (not old tools/ with hardcoded STEP-02-B)
from src.tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
from src.tools.terminal import run_command

from src.ticket_io import load_ticket as _io_load_ticket
from src.operator_v7 import Ticket, TicketStatus

from src.skill_store import match_goal_class, load_skill, write_skill, SkillLoadError, SkillWriteError

from agent.log_manager import prune_logs
from agent.context_budget import ContextBudget
from agent.sequence_gate import SequenceGate, LawViolationError


# ── config ────────────────────────────────────────────────────────────────────

def load_settings(path: str = "settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG          = load_settings()
MODEL        = CFG["model"]["id"]
ENDPOINT     = CFG["model"]["endpoint"]
API_KEY      = CFG["model"]["api_key"]
TEMPERATURE  = float(CFG["model"].get("temperature", 0.2))
TIMEOUT      = int(CFG["model"].get("timeout_seconds", 90))
MAX_RETRIES  = int(CFG["model"].get("max_retries", 2))
RETRY_DELAY  = 4

OPEN_DIR     = CFG["tickets"]["open_dir"]
CLOSED_DIR   = CFG["tickets"]["closed_dir"]
FAIL_DIR     = CFG["tickets"].get("failed_dir", "tickets/failed")
IN_PROG_DIR  = CFG["tickets"].get("in_progress_dir", "tickets/in_progress")
EXEC_SANDBOX = "output"
LOG_DIR      = CFG["logging"]["dir"].rstrip("/")

# Per-ticket max retries (fallback to model.max_retries)
MAX_TICKET_RETRIES = int(CFG["tickets"].get("max_retries_default", MAX_RETRIES))

for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR, IN_PROG_DIR, EXEC_SANDBOX, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# Audit JSONL path for skill cache hits
AUDIT_JSONL = os.path.join(LOG_DIR, "audit.jsonl")
JOURNAL_PATH = os.path.join(LOG_DIR, "luffy-journal.jsonl")

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)

# Session UUID — generated once per runner invocation
SESSION_UUID = str(uuid.uuid4())

# Context budget manager (graphify-inspired SHA256 cache, 64K window)
_ctx_cfg = CFG.get("context", {})
CTX_BUDGET = ContextBudget(
    ctx_limit=int(_ctx_cfg.get("ctx_limit", 65536)),
    cache_path=_ctx_cfg.get("cache_path", "logs/ctx-cache.json"),
    zones=_ctx_cfg.get("zones"),
)

# Sequence gate (journal + commit enforcement)
_seq_cfg = CFG.get("sequence", {})
SEQ_GATE = SequenceGate(
    journal_path=JOURNAL_PATH,
    agent_id=_seq_cfg.get("agent_id", "luffy-v1"),
    enforce_journal=bool(_seq_cfg.get("enforce_journal", True)),
    enforce_commit=bool(_seq_cfg.get("enforce_commit", True)),
)


# ── journal helpers (BUG 7 FIX: session lifecycle events) ─────────────────────

def append_journal(event: dict) -> None:
    """Append a JSONL event to logs/luffy-journal.jsonl."""
    if "ts" not in event:
        event["ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event.setdefault("session", SESSION_UUID)
    os.makedirs(os.path.dirname(JOURNAL_PATH) if os.path.dirname(JOURNAL_PATH) else ".", exist_ok=True)
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ── scratch file system (BUG 3 FIX: ported from MUMPS_Bot) ──────────────────

def scratch_append(ticket_id: str, event: dict) -> None:
    """Append a JSONL event to the ticket's scratch file."""
    scratch = os.path.join(LOG_DIR, f"scratch-{ticket_id}.jsonl")
    event.setdefault("ts", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    event.setdefault("ticket", ticket_id)
    with open(scratch, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def validate_scratch(ticket_id: str, num_steps: int) -> tuple:
    """Validate scratch file has REASONING + VERIFY for every step.

    Returns (ok: bool, reason: str).
    """
    scratch = os.path.join(LOG_DIR, f"scratch-{ticket_id}.jsonl")
    if not os.path.exists(scratch):
        return False, f"scratch file missing: {scratch}"

    events = []
    with open(scratch) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    has_init = any(e.get("event") == "SCRATCH_INIT" for e in events)
    if not has_init:
        return False, "scratch missing SCRATCH_INIT"

    for step_num in range(1, num_steps + 1):
        has_reasoning = any(
            e.get("event") == "REASONING" and e.get("step") == step_num
            for e in events
        )
        has_verify = any(
            e.get("event") == "VERIFY" and e.get("step") == step_num and e.get("pass") is True
            for e in events
        )
        if not has_reasoning:
            return False, f"scratch missing REASONING for step {step_num}"
        if not has_verify:
            return False, f"scratch missing passing VERIFY for step {step_num}"

    return True, "ok"


# ── tools (must be defined before REGISTRY) ────────────────────────────────────

def tool_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"ERROR: file not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tool_write_file(path: str, content: str) -> str:
    if path.endswith(".py") and os.path.dirname(path) == "":
        original_path = path
        path = os.path.join("output", path)
        print(f"  [tool] auto-sandbox: {original_path} → {path}")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"OK: wrote {len(content)} bytes to {path}"


def tool_list_dir(path: str) -> str:
    if not os.path.exists(path):
        return f"ERROR: directory not found: {path}"
    entries = sorted(os.listdir(path))
    if not entries:
        return f"EMPTY: {path}"
    return "\n".join(entries)


def tool_exec_python(path: str, timeout: int = 30) -> str:
    abs_path    = os.path.abspath(path)
    abs_sandbox = os.path.abspath(EXEC_SANDBOX)
    if not abs_path.startswith(abs_sandbox):
        return f"ERROR: exec_python blocked — path must be inside {EXEC_SANDBOX}/ (got {path})"
    if not os.path.exists(abs_path):
        return f"ERROR: file not found: {path}"
    try:
        result = subprocess.run(
            [sys.executable, abs_path],
            capture_output=True, text=True, timeout=timeout
        )
        lines = []
        if result.stdout.strip():
            lines.append(f"STDOUT:\n{result.stdout.strip()}")
        if result.stderr.strip():
            lines.append(f"STDERR:\n{result.stderr.strip()}")
        lines.append(f"returncode: {result.returncode}")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return f"ERROR: exec_python timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


# ── module-level registry ───────────────────────────────────────────────────────

REGISTRY = ToolRegistry()
REGISTRY.register("read_file",   tool_read_file,   {"path": {"type": str}})
REGISTRY.register("write_file",  tool_write_file,  {"path": {"type": str}, "content": {"type": str}})
REGISTRY.register("list_dir",    tool_list_dir,    {"path": {"type": str}})
REGISTRY.register("exec_python", tool_exec_python, {"path": {"type": str}})
REGISTRY.register("run_command", run_command,      {"cmd": {"type": list}})


# ── token budget ──────────────────────────────────────────────────────────────

CONTEXT_WINDOW  = int(CFG["model"].get("context_window", 8192))
BUDGET_PCT      = float(CFG["model"].get("output_budget_pct", 0.8))
BUDGET_CEILING  = int(CONTEXT_WINDOW * BUDGET_PCT)
BUDGET_FLOOR    = 1024

WORDS_PER_TOKEN = 0.75

def token_budget(ticket: Ticket) -> int:
    task_words = len(str(ticket.task or "").split())
    estimate   = int(task_words / WORDS_PER_TOKEN * 24)
    budget     = max(BUDGET_FLOOR, min(estimate, BUDGET_CEILING))
    max_tok    = ticket.max_tokens
    return int(max_tok) if max_tok is not None else budget


# ── hardware snapshot ─────────────────────────────────────────────────────────

def hw_snap() -> dict:
    snap = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        import psutil
        vm = psutil.virtual_memory()
        snap["ram_used_gb"]  = round(vm.used  / 1024**3, 2)
        snap["ram_total_gb"] = round(vm.total / 1024**3, 2)
        snap["cpu_pct"]      = psutil.cpu_percent(interval=0.1)
    except Exception:
        pass
    try:
        import urllib.request
        req  = urllib.request.urlopen(f"{ENDPOINT}/models", timeout=2)
        data = json.loads(req.read())
        snap["lemonade_loaded"] = [m["id"] for m in data.get("data", [])]
    except Exception:
        snap["lemonade_loaded"] = []
    return snap


# ── JSONL attempt log ─────────────────────────────────────────────────────────

def append_attempt_log(ticket_id: str, attempt: int, outcome: str,
                       tokens: int, elapsed: float, finish: str,
                       budget: int, tool_calls: int, reason: str,
                       hw_pre: dict, hw_post: dict) -> None:
    """Append one JSONL line to logs/<ticket_id>-attempts.jsonl."""
    log_path = os.path.join(LOG_DIR, f"{ticket_id}-attempts.jsonl")
    record = {
        "ts":          time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ticket_id":   ticket_id,
        "attempt":     attempt,
        "outcome":     outcome,
        "tokens":      tokens,
        "elapsed_s":   round(elapsed, 3),
        "tok_s":       round(tokens / elapsed, 1) if elapsed > 0 else 0,
        "finish":      finish,
        "budget":      budget,
        "tool_calls":  tool_calls,
        "reason":      reason,
        "ram_pre_gb":  hw_pre.get("ram_used_gb", None),
        "ram_post_gb": hw_post.get("ram_used_gb", None),
        "cpu_pre_pct": hw_pre.get("cpu_pct", None),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  [log] attempt record → {log_path}")


# ── ticket helpers ────────────────────────────────────────────────────────────

def load_ticket(path: str) -> Ticket:
    """Load a YAML ticket and return a fully-populated typed Ticket dataclass."""
    return _io_load_ticket(path)


def save_ticket(path: str, ticket) -> None:
    """Write ticket to YAML. Accepts Ticket dataclass or plain dict (decompose path)."""
    from src.ticket_io import save_ticket as _io_save_ticket
    if isinstance(ticket, Ticket):
        _io_save_ticket(path, ticket)
    else:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


def scan_open() -> list:
    return sorted(glob.glob(os.path.join(OPEN_DIR, "*.yaml")))


def is_closed(ticket_id: str) -> bool:
    return os.path.exists(os.path.join(CLOSED_DIR, f"{ticket_id}.yaml"))


def is_failed(ticket_id: str) -> bool:
    return os.path.exists(os.path.join(FAIL_DIR, f"{ticket_id}.yaml"))


def deps_met(ticket: Ticket) -> bool:
    return all(is_closed(d) for d in (ticket.depends_on or []))


def _detect_deadlock(open_tickets: dict) -> set | None:
    """DFS cycle detection for ticket dependency graph."""
    graph = {}
    for tid, ticket in open_tickets.items():
        deps = ticket.get("depends_on", []) or []
        graph[tid] = [d for d in deps if d in open_tickets]

    color = {tid: 0 for tid in graph}

    def dfs(node: str, path: list) -> set | None:
        if node not in color:
            return None
        if color[node] == 1:
            cycle_start = path.index(node)
            return set(path[cycle_start:])
        if color[node] == 2:
            return None
        color[node] = 1
        path.append(node)
        for neighbor in graph.get(node, []):
            result = dfs(neighbor, path)
            if result is not None:
                return result
        path.pop()
        color[node] = 2
        return None

    for node in graph:
        if color[node] == 0:
            result = dfs(node, [])
            if result is not None:
                return result
    return None


def _consumes_met(ticket: Ticket) -> bool:
    """Check if all consumed artifacts from dependencies are available."""
    consumes = ticket.consumes or []
    if not consumes:
        return True
    for consumed_path in consumes:
        if os.path.exists(consumed_path):
            continue
        deps = ticket.depends_on or []
        found = False
        for dep_id in deps:
            result_file = os.path.join(LOG_DIR, f"{dep_id}-result.txt")
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as f:
                    if consumed_path in f.read():
                        found = True
                        break
        if found:
            continue
        for dep_id in deps:
            if is_closed(dep_id):
                closed_path = os.path.join(CLOSED_DIR, f"{dep_id}.yaml")
                if os.path.exists(closed_path):
                    with open(closed_path, 'r', encoding='utf-8') as f:
                        if consumed_path in f.read():
                            found = True
                            break
        if not found:
            return False
    return True


def next_ticket_id() -> str:
    nums = []
    for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR]:
        for p in glob.glob(os.path.join(d, "TASK-*.yaml")):
            stem = os.path.basename(p).replace(".yaml", "")
            try:
                nums.append(int(stem.split("-")[1]))
            except (IndexError, ValueError):
                pass
    return f"TASK-{max(nums, default=0) + 1:03d}"


# ── result forwarding ─────────────────────────────────────────────────────────

def result_summary(result_path: str) -> str:
    if not os.path.exists(result_path):
        return ""
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()
    marker = "=== tool results ==="
    if marker in content:
        return content.split(marker, 1)[1].strip()[:800]
    return content.strip()[:800]


def inject_upstream_context(ticket: Ticket) -> str:
    deps = ticket.depends_on or []
    if not deps:
        return ""
    blocks = []
    for dep_id in deps:
        closed_path = os.path.join(CLOSED_DIR, f"{dep_id}.yaml")
        if not os.path.exists(closed_path):
            continue
        dep_ticket  = load_ticket(closed_path)
        result_path = dep_ticket.result_path or f"{LOG_DIR}/{dep_id}-result.txt"
        summary     = result_summary(result_path)
        if summary:
            blocks.append(f"--- output of {dep_id} ---\n{summary}")
    return "\n\n".join(blocks)


# ── gate runner (BUG 5 FIX: ported from MUMPS_Bot) ──────────────────────────

def run_gate(ticket: Ticket) -> tuple:
    """Run the ticket's gate_command as a subprocess acceptance test.

    Returns (passed: bool, output: str).
    """
    cmd = ticket.gate_command or ""
    if not cmd:
        return True, "no gate defined"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=".", timeout=60
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "gate_command timed out (60s)"
    except Exception as e:
        return False, f"gate_command error: {e}"


# ── model call ────────────────────────────────────────────────────────────────

def call_model(messages: list, budget: int) -> tuple:
    # BUG 10 FIX: exactly MAX_RETRIES + 1 total attempts (initial + retries)
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            t0       = time.perf_counter()
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=budget,
                temperature=TEMPERATURE,
                timeout=TIMEOUT,
            )
            elapsed = round(time.perf_counter() - t0, 2)

            if not response.choices:
                print(f"  [model] attempt {attempt}/{MAX_RETRIES+1}: empty choices — retry in {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
                continue

            choice = response.choices[0]
            raw    = (choice.message.content or "") if choice.message else ""
            tokens = response.usage.total_tokens if response.usage else 0
            finish = choice.finish_reason or "unknown"

            if not raw.strip():
                print(f"  [model] attempt {attempt}/{MAX_RETRIES+1}: empty content — retry in {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
                continue

            return raw, tokens, finish, elapsed

        except Exception as e:
            print(f"  [model] attempt {attempt}/{MAX_RETRIES+1}: {e}")
            if attempt < MAX_RETRIES + 1:
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"model call failed after {MAX_RETRIES + 1} attempts")


# ── parser ────────────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(r'^[ \t]+(TOOL:|PATH:|END$|DONE$)', re.MULTILINE)

def normalise(text: str) -> str:
    return _HEADER_RE.sub(lambda m: m.group(1), text)


BLOCK_RE = re.compile(
    r'TOOL:\s*(\S+)\s*\nPATH:\s*(.+?)\s*\n(?:CONTENT:\n([\s\S]*?)\nEND|END)',
    re.MULTILINE
)


def parse_and_run_tools(response_text: str, ticket_id: str = "", exec_timeout: int = 30) -> list:
    results = []
    step_n = 0
    for match in BLOCK_RE.finditer(normalise(response_text)):
        step_n += 1
        tool    = match.group(1).strip()
        path    = match.group(2).strip()
        content = match.group(3)
        print(f"  [tool] {tool} → {path}")

        # Scratch: REASONING event before tool call
        if ticket_id:
            scratch_append(ticket_id, {
                "event": "REASONING", "step": step_n,
                "decomposition": f"Execute {tool} on {path}",
                "ground_truth": f"Tool {tool} is registered and path is valid",
                "constraints": f"Output sandbox: {EXEC_SANDBOX}/",
                "minimal_transform": f"Single {tool} call",
            })

        # Journal: TOOL_CALL pending
        if ticket_id:
            append_journal({
                "event": "TOOL_CALL", "ticket": ticket_id,
                "tool": tool, "args": {"path": path}, "status": "pending",
            })

        t_start = time.perf_counter()
        try:
            if tool == "write_file":
                result = REGISTRY.call(tool, {"path": path, "content": content or ""})
            elif tool == "run_command":
                result = REGISTRY.call(tool, {"cmd": path.split()})
            else:
                result = REGISTRY.call(tool, {"path": path})
        except (ToolNotFoundError, ToolArgError) as e:
            result = f"ERROR: {e}"
        t_elapsed_ms = int((time.perf_counter() - t_start) * 1000)

        result_str = str(result) if isinstance(result, dict) else result
        is_error = isinstance(result_str, str) and result_str.startswith("ERROR:")
        print(f"  [tool] result: {result_str[:120]}")

        # Journal: TOOL_CALL ok/error
        if ticket_id:
            append_journal({
                "event": "TOOL_CALL", "ticket": ticket_id,
                "tool": tool, "status": "error" if is_error else "ok",
                "elapsed_ms": t_elapsed_ms,
            })

        # Scratch: VERIFY event after tool call
        if ticket_id:
            scratch_append(ticket_id, {
                "event": "VERIFY", "step": step_n,
                "expected": f"{tool} succeeds without ERROR",
                "actual": result_str[:200] if result_str else "empty",
                "pass": not is_error,
            })

        results.append((tool, path, result))
    return results


# ── prompt ────────────────────────────────────────────────────────────────

TOOL_SYNTAX = """\
TOOL: read_file
PATH: <path>
END

TOOL: write_file
PATH: <path>
CONTENT:
<content>
END

TOOL: list_dir
PATH: <path>
END

TOOL: exec_python
PATH: <path>
END
"""


def build_prompt(ticket: Ticket, upstream_context: str, ticket_id: str = "") -> str:
    prompt  = TOOL_SYNTAX
    prompt += f"\nTask: {ticket.task}"
    for cf in (ticket.context_files or []):
        # Context budget check: skip files already in context (graphify cache pattern)
        should, reason = CTX_BUDGET.should_read(cf, zone="ticket_context")
        if should:
            content = tool_read_file(cf)
            CTX_BUDGET.mark_read(cf, zone="ticket_context")
            prompt += f"\n\n--- {cf} ---\n{content}"
        else:
            summary = CTX_BUDGET.get_read_summary(cf) or f"[{reason}]"
            print(f"  [ctx] SKIP {cf} — {summary}")
            # Law §3: emit LAW3_CACHE_HIT on cache skip (severity: info, NOT a violation)
            if ticket_id:
                append_journal({
                    "event": "LAW3_CACHE_HIT",
                    "ticket": ticket_id,
                    "path": cf,
                    "severity": "info",
                    "detail": f"Context budget cache hit — {summary}",
                })
            prompt += f"\n\n--- {cf} {summary} ---"
    if upstream_context.strip():
        prompt += f"\n\n--- upstream results ---\n{upstream_context}"
    return prompt


# ── failure handling (BUG 6 FIX: ported from MUMPS_Bot) ──────────────────────

def _handle_failure(ticket: Ticket, ticket_path: str, reason: str) -> bool:
    """Move ticket to failed/, write to ISSUE.md, emit journal event."""
    ticket_id = ticket.id

    # Move to failed/
    ticket.status = TicketStatus.ESCALATED
    extras = getattr(ticket, "_extras", {})
    extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    extras["failure_reason"] = reason
    object.__setattr__(ticket, "_extras", extras)

    # Remove from in_progress if present
    ip_path = os.path.join(IN_PROG_DIR, f"{ticket_id}.yaml")
    if os.path.exists(ip_path):
        os.remove(ip_path)

    fail_path = os.path.join(FAIL_DIR, f"{ticket_id}.yaml")
    save_ticket(fail_path, ticket)

    # Remove from open if still there
    if os.path.exists(ticket_path) and ticket_path != fail_path:
        os.remove(ticket_path)

    # Scratch cleanup: close and rename to -FAILED
    scratch_path = os.path.join(LOG_DIR, f"scratch-{ticket_id}.jsonl")
    if os.path.exists(scratch_path):
        scratch_append(ticket_id, {"event": "SCRATCH_CLOSE", "result": "FAILED"})
        failed_scratch = os.path.join(LOG_DIR, f"scratch-{ticket_id}-FAILED.jsonl")
        shutil.move(scratch_path, failed_scratch)

    # Journal event
    append_journal({
        "event": "TICKET_FAILED", "ticket": ticket_id,
        "attempts": ticket.attempts,
        "reason": reason.splitlines()[0][:120] if reason else "unknown",
        "scratch_path": f"logs/scratch-{ticket_id}-FAILED.jsonl",
    })

    # Append to ISSUE.md
    issue_path = "ISSUE.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    iss_id = f"ISS-{ticket_id}-{ts}"
    with open(issue_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {iss_id}\n\n")
        f.write(f"- `status: open`\n")
        f.write(f"- `blocked_on: human`\n")
        f.write(f"- `ticket: {ticket_id}`\n")
        f.write(f"- `reason: {reason.splitlines()[0][:120] if reason else 'unknown'}`\n")
        f.write(f"- `action_required: Review failure, fix ticket or context, reset status to open`\n")

    print(f"  ❌  {ticket_id} FAILED: {reason.splitlines()[0][:80] if reason else 'unknown'}")
    print(f"     See ISSUE.md and logs/ for details.")
    return False


# ── execute one ticket ────────────────────────────────────────────────────────

def execute_ticket(ticket_path: str) -> bool:
    ticket      = load_ticket(ticket_path)
    ticket_id   = ticket.id
    result_path = ticket.result_path or f"{LOG_DIR}/{ticket_id}-result.txt"
    attempt_n   = ticket.attempts + 1

    print(f"\n[runner] ── {ticket_id} (attempt {attempt_n}) ──")

    # BUG 4 FIX: Move to in_progress before execution
    ip_path = os.path.join(IN_PROG_DIR, f"{ticket_id}.yaml")
    ticket.status = TicketStatus.PENDING  # in_progress maps to pending in enum
    extras = getattr(ticket, "_extras", {})
    extras["status"] = "in_progress"
    object.__setattr__(ticket, "_extras", extras)
    save_ticket(ip_path, ticket)
    if os.path.exists(ticket_path) and os.path.abspath(ticket_path) != os.path.abspath(ip_path):
        os.remove(ticket_path)

    # Journal: TICKET_START
    append_journal({
        "event": "TICKET_START", "ticket": ticket_id,
        "attempt": attempt_n, "deps_satisfied": True,
    })

    # Create scratch file (BUG 3 FIX)
    scratch_append(ticket_id, {"event": "SCRATCH_INIT", "attempt": attempt_n})

    # Law §2 enforcement: verify SCRATCHPAD_READ was emitted in drain()
    journal_path = os.path.join(LOG_DIR, "luffy-journal.jsonl")
    scratchpad_read_found = False
    if os.path.exists(journal_path):
        with open(journal_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("event") == "SCRATCHPAD_READ":
                        scratchpad_read_found = True
                        break
                except json.JSONDecodeError:
                    continue
    if not scratchpad_read_found:
        append_journal({
            "event": "LAW_VIOLATION",
            "law": 2,
            "ticket": ticket_id,
            "detail": "SCRATCHPAD_READ not found in drain() — Law §2 violated",
            "hard_block": True,
        })
        return _handle_failure(ticket, ip_path, "Law §2 VIOLATION: SCRATCHPAD_READ not emitted in drain()")

    # STEP-06-B: Skill cache check
    try:
        if ticket.task:
            goal_class = match_goal_class(ticket.task)
            if goal_class:
                skill = load_skill(goal_class)
                if skill:
                    print(f"[runner] cache hit: {goal_class}")
                    tool_sequence = skill.get("tool_sequence", [])
                    tool_results = []
                    for tool_call in tool_sequence:
                        tool_name = tool_call.get("tool")
                        tool_args = tool_call.get("args", {})
                        result = REGISTRY.call(tool_name, tool_args)
                        tool_results.append((tool_name, tool_args.get("path", "unknown"), result))
                        print(f"[runner] skill tool: {tool_name} → {tool_args.get('path', 'unknown')}")
                    result_str = "\n".join(str(r) for r in tool_results)
                    with open(result_path, "w") as f:
                        f.write(result_str)
                    ticket.status = TicketStatus.CLOSED
                    extras = getattr(ticket, "_extras", {})
                    extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    extras["skill_cache_hit"] = True
                    object.__setattr__(ticket, "_extras", extras)
                    audit_entry = {
                        "ticket_id": ticket_id, "goal_class": goal_class,
                        "source": "skill_cache", "cache_hit": True,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    with open(AUDIT_JSONL, "a") as f:
                        f.write(json.dumps(audit_entry) + "\n")
                    closed_path = os.path.join(CLOSED_DIR, f"{ticket_id}.yaml")
                    save_ticket(closed_path, ticket)
                    # Clean up in_progress
                    if os.path.exists(ip_path):
                        os.remove(ip_path)
                    print(f"[runner] skill-cached result → {closed_path}")
                    # BUG 8 FIX: write_skill expects a dict with required keys
                    write_skill(goal_class, {
                        "goal_class": goal_class,
                        "tool_sequence": tool_sequence,
                        "elapsed_s": 0.0,
                    })
                    # Journal + scratch close
                    append_journal({"event": "TICKET_CLOSED", "ticket": ticket_id,
                                    "attempt": attempt_n, "wall_sec": 0.0,
                                    "tokens_in": None, "tokens_out": None})
                    scratch_append(ticket_id, {"event": "SCRATCH_CLOSE", "result": "CLOSED"})
                    scratch_path = os.path.join(LOG_DIR, f"scratch-{ticket_id}.jsonl")
                    if os.path.exists(scratch_path):
                        os.remove(scratch_path)
                    return True
    except Exception as e:
        print(f"[runner] skill execution failed: {e}")
        # Fall through to model fallback

    upstream = inject_upstream_context(ticket)
    prompt   = build_prompt(ticket, upstream)
    budget   = token_budget(ticket)

    print(f"  [runner] budget={budget}  deps_context={'yes' if upstream else 'no'}")

    hw_pre = hw_snap()
    print(f"  [hw] RAM {hw_pre.get('ram_used_gb','?')}/{hw_pre.get('ram_total_gb','?')} GB  "
          f"CPU {hw_pre.get('cpu_pct','?')}%")

    # Journal: TOOL_CALL pending for model
    append_journal({"event": "TOOL_CALL", "ticket": ticket_id,
                    "tool": "model_call", "args": {"model": MODEL}, "status": "pending"})

    t_start = time.perf_counter()
    try:
        raw, tokens, finish, elapsed = call_model(
            messages=[
                {"role": "system",
                 "content": "Output ONLY raw tool blocks. TOOL/PATH/END lines have no leading whitespace."},
                {"role": "user", "content": prompt},
            ],
            budget=budget,
        )
    except RuntimeError as e:
        hw_post = hw_snap()
        t_elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        append_journal({"event": "TOOL_CALL", "ticket": ticket_id,
                        "tool": "model_call", "status": "error", "elapsed_ms": t_elapsed_ms,
                        "error": str(e)})
        append_attempt_log(ticket_id, attempt_n, "error", 0, 0.0, "error",
                           budget, 0, str(e), hw_pre, hw_post)
        print(f"  [runner] model call failed: {e}")
        _write_result(result_path, ticket_id, "error", 0, str(e), 0.0,
                      hw_pre, hw_post, [], str(e), raw_full=str(e))
        return _handle_failure(ticket, ip_path, f"Model call failed: {e}")

    hw_post = hw_snap()
    t_elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    tok_s   = round(tokens / elapsed, 1) if elapsed > 0 else 0
    print(f"  [runner] tokens={tokens}  elapsed={elapsed}s  tok/s={tok_s}  finish={finish}")

    # Journal: TOOL_CALL ok for model
    append_journal({"event": "TOOL_CALL", "ticket": ticket_id,
                    "tool": "model_call", "status": "ok", "elapsed_ms": t_elapsed_ms})

    tool_results = parse_and_run_tools(raw, ticket_id=ticket_id, exec_timeout=TIMEOUT)
    passed, reason = _evaluate(result_path, tool_results)

    # BUG 5 FIX: Run gate_command if present
    if passed and ticket.gate_command:
        print(f"  [runner] running gate: {ticket.gate_command}")
        append_journal({"event": "GATE_RUN", "ticket": ticket_id,
                        "command": ticket.gate_command, "status": "pending"})
        gate_passed, gate_output = run_gate(ticket)
        append_journal({"event": "GATE_RUN", "ticket": ticket_id,
                        "command": ticket.gate_command,
                        "status": "pass" if gate_passed else "fail"})
        if not gate_passed:
            passed = False
            reason = f"gate_command failed: {gate_output.splitlines()[0][:80] if gate_output else 'unknown'}"

    outcome = "pass" if passed else "fail"

    append_attempt_log(ticket_id, attempt_n, outcome, tokens, elapsed, finish,
                       budget, len(tool_results), reason, hw_pre, hw_post)

    _write_result(result_path, ticket_id, finish, tokens, raw, elapsed,
                  hw_pre, hw_post, tool_results, reason, raw_full=raw)

    # Law §1 enforcement: scratch must have non-INIT events
    try:
        SEQ_GATE.assert_scratch_written(ticket_id)
    except LawViolationError as e:
        append_journal({
            "event": "LAW_VIOLATION", "law": 1, "ticket": ticket_id,
            "detail": str(e),
        })
        return _handle_failure(ticket, ip_path, f"Law §1 VIOLATION: {str(e)}")

    if passed:
        ticket.status = TicketStatus.CLOSED
        ticket.attempts = attempt_n
        extras = getattr(ticket, "_extras", {})
        extras["updated_at"]   = time.strftime("%Y-%m-%dT%H:%M:%S")
        extras["attempts_log"] = f"{LOG_DIR}/{ticket_id}-attempts.jsonl"
        extras["latency_s"]    = round(elapsed, 2)
        extras["tokens_used"]  = tokens
        object.__setattr__(ticket, "_extras", extras)
        dest = os.path.join(CLOSED_DIR, f"{ticket_id}.yaml")
        save_ticket(dest, ticket)
        prune_logs(
            log_dir=LOG_DIR,
            fail_dir=FAIL_DIR,
            max_on_disk=int(CFG["logging"].get("max_logs", 100)),
            min_retain=int(CFG["logging"].get("min_retain", 10)),
            keep_escalated=bool(CFG["logging"].get("keep_escalated", True)),
        )
        # Clean up in_progress
        if os.path.exists(ip_path):
            os.remove(ip_path)
        # Journal + scratch close
        append_journal({"event": "TICKET_CLOSED", "ticket": ticket_id,
                        "attempt": attempt_n, "wall_sec": round(elapsed, 2),
                        "tokens_in": None, "tokens_out": tokens or None})
        scratch_append(ticket_id, {"event": "SCRATCH_CLOSE", "result": "CLOSED"})
        scratch_path = os.path.join(LOG_DIR, f"scratch-{ticket_id}.jsonl")
        if os.path.exists(scratch_path):
            os.remove(scratch_path)
        print(f"  ✅  {ticket_id} CLOSED ({elapsed:.1f}s, {tokens} tokens)")
        return True
    else:
        print(f"  [runner] FAIL: {reason}")
        # Don't call _handle_failure here — let drain() decide retry vs fail
        return False


def _evaluate(result_path: str, tool_results: list) -> tuple:
    if not tool_results:
        return False, "no tool calls detected"
    for tool, path, result in tool_results:
        if isinstance(result, str) and result.startswith("ERROR:"):
            return False, f"{tool}:{path} → {result[:80]}"
        if isinstance(result, str) and "returncode:" in result:
            rc = re.search(r'returncode:\s*(\d+)', result)
            if rc and rc.group(1) != "0":
                return False, f"non-zero returncode: {rc.group(1)}"
    return True, "ok"


def _write_result(result_path, ticket_id, finish, tokens, raw, elapsed,
                  hw_pre, hw_post, tool_results, reason="ok", raw_full=None):
    os.makedirs(os.path.dirname(result_path) if os.path.dirname(result_path) else ".",
                exist_ok=True)
    lines = [
        f"ticket:   {ticket_id}",
        f"finish:   {finish}",
        f"tokens:   {tokens}",
        f"elapsed:  {elapsed}s",
        f"reason:   {reason}",
        "",
        "=== hardware ===",
        f"pre:  RAM {hw_pre.get('ram_used_gb','?')}/{hw_pre.get('ram_total_gb','?')} GB  "
        f"CPU {hw_pre.get('cpu_pct','?')}%",
        f"post: RAM {hw_post.get('ram_used_gb','?')}/{hw_post.get('ram_total_gb','?')} GB  "
        f"CPU {hw_post.get('cpu_pct','?')}%",
        f"tok/s: {round(tokens/elapsed,1) if elapsed>0 else 0}",
        "",
        "=== tool results ===",
    ]
    if tool_results:
        for tool, path, result in tool_results:
            lines += [f"[{tool}] {path}", str(result), ""]
    else:
        lines += ["no tool calls detected", ""]
    lines += [
        "=== raw model response (complete) ===",
        raw_full if raw_full is not None else raw,
    ]
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── decompose ─────────────────────────────────────────────────────────────────

DECOMPOSE_SYSTEM = """You are a task decomposer for an agentic coding system. Output ONLY YAML tickets in a YAML list format.

CRITICAL PATH RULES (violations cause exec_python to be blocked by the sandbox):
- exec_python: path MUST begin with 'output/' — NEVER a bare filename like 'fib.py'
- write_file: when paired with exec_python, use 'output/<name>.py' for BOTH the write and exec paths
- Example correct pair: write_file PATH=output/solution.py then exec_python PATH=output/solution.py
- Example WRONG: write_file PATH=solution.py (bare filename — will be auto-corrected but exec still fails)

TICKET VERBOSITY RULES (required for Graphify knowledge graph integration):
- task: describe the COMPLETE intent — what to write, exactly where (output/ for .py),
  what to verify, what the expected output/artifact is, and why this task exists
  in the workflow. Be explicit about the tool sequence. Minimum 3 sentences.
- rationale: why this task exists in the pipeline — its role in the broader workflow
- produces: list of file paths or contracts this task creates (e.g. [output/fib.py, stdout:fibonacci-sequence])
- consumes: list of artifacts/outputs from depends_on tasks this ticket reads
- tags: semantic labels for graph clustering (e.g. [math, fibonacci, numeric-output, verification])

GENERAL RULES:
- Each ticket: 1-3 tool calls. Tools: write_file, exec_python, read_file, list_dir.
- Use depends_on for hard data-flow dependencies.
- Output ONLY valid YAML list — no markdown fences, no explanation, no text before or after.
- Start ticket IDs from TASK-XXX as specified.

Output format example:
- ticket_id: TASK-001
  title: "Generate Fibonacci sequence to output/fib.py and execute"
  task: >
    Write a Python script to output/fib.py that prints the first 10 Fibonacci
    numbers, one per line. Execute the script via exec_python using path output/fib.py.
    Verify that the output contains '55' (the 10th Fibonacci number).
  rationale: Establishes the base numeric output artifact.
  produces: [output/fib.py, stdout:fibonacci-10]
  consumes: []
  tags: [fibonacci, numeric-output, write-and-exec, foundation]
  depends_on: []
  allowed_tools: [write_file, exec_python]
  agent: Qwen3.5-35B-A3B-GGUF"""


def decompose_goal(goal: str, first_n: int) -> list:
    print(f"[runner] decomposing goal...")
    messages = [
        {"role": "system", "content": DECOMPOSE_SYSTEM},
        {"role": "user",
         "content": (
             f"Goal: {goal}\n"
             f"Start ticket numbering from TASK-{first_n:03d}.\n"
             f"Output ONLY the YAML list."
         )},
    ]
    decompose_budget = CFG["model"].get("decompose_budget")
    if decompose_budget is None:
        decompose_budget = 2048
    decompose_budget = min(int(decompose_budget), BUDGET_CEILING)
    try:
        raw, tokens, finish, elapsed = call_model(messages, budget=decompose_budget)
    except RuntimeError as e:
        print(f"[runner] decompose failed: {e}")
        return []
    print(f"[runner] decompose: {tokens} tokens  elapsed={elapsed}s  finish={finish}")
    cleaned = re.sub(r'^```[\w]*\n?', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'```$', '', cleaned.strip())
    try:
        tickets = yaml.safe_load(cleaned)
        if not isinstance(tickets, list):
            print(f"[runner] decompose: expected list, got {type(tickets).__name__}")
            print(f"[runner] decompose raw:\n{raw[:400]}")
            return []
        return tickets
    except yaml.YAMLError as e:
        print(f"[runner] YAML parse error: {e}")
        print(f"[runner] decompose raw:\n{raw[:400]}")
        return []


def write_tickets(tickets: list) -> None:
    for t in tickets:
        tid = t.get("ticket_id", next_ticket_id())
        t.setdefault("status",        "open")
        t.setdefault("depth",         0)
        t.setdefault("attempts",      0)
        t.setdefault("max_depth",     2)
        t.setdefault("max_retries",   MAX_TICKET_RETRIES)
        t.setdefault("created_at",    time.strftime("%Y-%m-%d"))
        t.setdefault("updated_at",    time.strftime("%Y-%m-%d"))
        t.setdefault("result_path",   f"{LOG_DIR}/{tid}-result.txt")
        t.setdefault("context_files", [])
        t.setdefault("rationale",     "")
        t.setdefault("produces",      [])
        t.setdefault("consumes",      [])
        t.setdefault("tags",          [])
        t.setdefault("agent",         MODEL)
        t.setdefault("task_steps",    [])
        t.setdefault("gate_command",  "")
        t.setdefault("acceptance_criteria", "")
        path = os.path.join(OPEN_DIR, f"{tid}.yaml")
        save_ticket(path, t)
        print(f"[runner] ticket → {path}")


# ── drain loop ────────────────────────────────────────────────────────────────

def drain(once: bool = False) -> None:
    max_retries = MAX_TICKET_RETRIES

    # Reset context budget for new session
    CTX_BUDGET.reset_session()

    # BUG 7 FIX: SESSION_START event
    append_journal({
        "event": "SESSION_START",
        "executor": MODEL,
        "stage": CFG.get("agent", {}).get("stage", "bud"),
    })

    # Law §2: read scratchpad, emit journal event
    scratchpad_path = "AI-FIRST/NEXT-STEPS.md"
    should, reason = CTX_BUDGET.should_read(scratchpad_path, zone="system_prompt")
    if should:
        scratchpad_content = tool_read_file(scratchpad_path)
        CTX_BUDGET.mark_read(scratchpad_path, zone="system_prompt")
        append_journal({
            "event": "SCRATCHPAD_READ",
            "path": scratchpad_path,
            "law": 2,
            "cached": False,
        })
    else:
        append_journal({
            "event": "SCRATCHPAD_READ",
            "path": scratchpad_path,
            "law": 2,
            "cached": True,
            "note": "CTX cache hit — scratchpad unchanged since last read",
        })

    session_start = time.perf_counter()
    tickets_closed = 0
    tickets_failed = 0

    prune_logs(
        log_dir=LOG_DIR,
        fail_dir=FAIL_DIR,
        max_on_disk=int(CFG["logging"].get("max_logs", 100)),
        min_retain=int(CFG["logging"].get("min_retain", 10)),
        keep_escalated=bool(CFG["logging"].get("keep_escalated", True)),
    )

    try:
        while True:
            tickets = scan_open()
            if not tickets:
                print("[runner] all tickets closed — done")
                break

            dispatched_this_pass = 0
            deferred = []

            for ticket_path in tickets:
                ticket    = load_ticket(ticket_path)
                ticket_id = ticket.id

                if not deps_met(ticket) or not _consumes_met(ticket):
                    unmet = [d for d in (ticket.depends_on or [])
                             if not is_closed(d)]
                    unmet_consumes = [c for c in (ticket.consumes or [])
                                      if not os.path.exists(c)]
                    reason = []
                    if unmet:
                        reason.append(f"waiting on deps {unmet}")
                    if unmet_consumes:
                        reason.append(f"missing consumes {unmet_consumes}")
                    print(f"[runner] deferred {ticket_id} — {'; '.join(reason)}")
                    deferred.append(ticket_path)
                    continue

                dispatched_this_pass += 1
                passed = execute_ticket(ticket_path)

                if passed:
                    tickets_closed += 1
                else:
                    # BUG 9 FIX: Proper retry loop — reload ticket from in_progress
                    ip_path = os.path.join(IN_PROG_DIR, f"{ticket_id}.yaml")
                    if os.path.exists(ip_path):
                        ticket = load_ticket(ip_path)
                    attempts = ticket.attempts + 1
                    ticket_max_retries = getattr(ticket, "max_retries", None) or max_retries

                    if attempts < ticket_max_retries:
                        # Move back to open for retry
                        ticket.attempts = attempts
                        ticket.status = TicketStatus.PENDING
                        extras = getattr(ticket, "_extras", {})
                        extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        extras["status"] = "open"
                        object.__setattr__(ticket, "_extras", extras)
                        retry_path = os.path.join(OPEN_DIR, f"{ticket_id}.yaml")
                        save_ticket(retry_path, ticket)
                        if os.path.exists(ip_path):
                            os.remove(ip_path)
                        append_journal({
                            "event": "TICKET_RETRY", "ticket": ticket_id,
                            "attempt": attempts,
                            "reason": "gate/tool failure, retrying",
                        })
                        print(f"  ⚠️  {ticket_id} retry queued (attempt {attempts}/{ticket_max_retries})")
                    else:
                        tickets_failed += 1
                        _handle_failure(ticket, ip_path,
                                        f"Max retries exhausted ({attempts}/{ticket_max_retries})")

                if once:
                    return

            if dispatched_this_pass == 0 and deferred:
                # Deadlock detection
                open_tickets = {}
                for p in deferred:
                    ticket = load_ticket(p)
                    open_tickets[ticket.id] = {"ticket_id": ticket.id, "depends_on": ticket.depends_on or []}

                cycle = _detect_deadlock(open_tickets)

                if cycle:
                    print(f"[runner] DEADLOCK DETECTED: cycle involving {cycle}")
                    for p in deferred:
                        ticket = load_ticket(p)
                        if ticket.id in cycle:
                            tickets_failed += 1
                            _handle_failure(ticket, p, f"Deadlock: cycle involving {cycle}")
                    break

                print(f"[runner] blocked — {len(deferred)} ticket(s) cannot proceed:")
                for p in deferred:
                    ticket    = load_ticket(p)
                    ticket_id = ticket.id
                    unmet         = [d for d in (ticket.depends_on or [])
                                     if not is_closed(d)]
                    failed_deps   = [d for d in unmet if is_failed(d)]
                    missing_deps  = [d for d in unmet
                                     if not is_failed(d)
                                     and not os.path.exists(os.path.join(OPEN_DIR, f"{d}.yaml"))]
                    open_deps     = [d for d in unmet
                                     if os.path.exists(os.path.join(OPEN_DIR, f"{d}.yaml"))]
                    if failed_deps:
                        print(f"  {ticket_id}: UPSTREAM FAILED → {failed_deps} exhausted retries")
                    elif missing_deps:
                        print(f"  {ticket_id}: MISSING DEP → {missing_deps} not found anywhere")
                    elif open_deps:
                        print(f"  {ticket_id}: DEADLOCK → circular dep on open tickets {open_deps}")
                    else:
                        print(f"  {ticket_id}: waiting on {unmet}")
                break
    finally:
        # BUG 7 FIX: SESSION_END event (always runs, even on exception)
        wall_sec = round(time.perf_counter() - session_start, 2)
        reason = "DONE" if tickets_failed == 0 else "ESCALATED"
        if not scan_open() and tickets_failed == 0:
            reason = "DONE"
        elif scan_open() and tickets_closed == 0 and tickets_failed == 0:
            reason = "BLOCKED"
        append_journal({
            "event": "SESSION_END",
            "reason": reason,
            "tickets_closed": tickets_closed,
            "tickets_failed": tickets_failed,
            "wall_sec": wall_sec,
            "context_budget": CTX_BUDGET.budget_report(),
            "sequence_completed": SEQ_GATE.completed,
        })


# ── pre-warm ──────────────────────────────────────────────────────────────────

def prewarm() -> None:
    print(f"[runner] pre-warming {MODEL}...")
    try:
        client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            timeout=60,
        )
        print(f"[runner] warm OK")
    except Exception as e:
        print(f"[runner] warm failed: {e}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Fractal Claws agent runner v7")
    parser.add_argument("--once", action="store_true", help="Run one ticket and exit")
    parser.add_argument("--no-prewarm", action="store_true", help="Skip model pre-warm")
    parser.add_argument("--goal", type=str, help="Decompose a goal into tickets first")
    parser.add_argument("--ticket", type=str, help="Run a specific ticket by ID")
    parser.add_argument("--dry-run", action="store_true", help="Print next ticket without executing")
    args = parser.parse_args()

    if not args.no_prewarm:
        prewarm()

    if args.dry_run:
        tickets = scan_open()
        if tickets:
            t = load_ticket(tickets[0])
            print(f"Next ready: {t.id} — {t.title}")
        else:
            print("No open tickets.")
        return

    if args.goal:
        print(f"[runner] goal: {args.goal}")
        existing_nums = []
        for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR]:
            for p in glob.glob(os.path.join(d, "TASK-*.yaml")):
                stem = Path(p).stem
                try:
                    existing_nums.append(int(stem.split("-")[1]))
                except (IndexError, ValueError):
                    pass
        first_n = max(existing_nums, default=0) + 1
        tickets = decompose_goal(args.goal, first_n)
        if not tickets:
            print("[runner] decomposition produced no tickets — abort")
            sys.exit(1)
        write_tickets(tickets)
        print(f"[runner] {len(tickets)} ticket(s) written")

    drain(once=args.once)


if __name__ == "__main__":
    main()
