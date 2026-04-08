#!/usr/bin/env python3
"""
runner.py — Fractal Claws agent skeleton v6

Single entry point. Reads all config from settings.yaml.
No model names, no depths, no tiers hardcoded here.

Usage:
    python agent/runner.py                        # drain all open tickets
    python agent/runner.py --goal "<goal>"        # decompose goal then drain
    python agent/runner.py --once                 # dispatch one ticket then exit
    python agent/runner.py --no-prewarm           # skip model pre-warm (fast start)

Budget policy (v4 — thinking-model aware):
    BUDGET_FLOOR   = 1024                   (minimum for thinking + tool block)
    BUDGET_CEILING = context_window * 0.8   (80% of ctx — matches AGENT-POLICY.md)
    token_budget() multiplier = *24         (thinking models need 3x headroom vs *8)
    max_tokens in settings.yaml = hard output CAP (doc-only; runner uses dynamic budget)
    decompose_budget in settings.yaml = output tokens for decompose YAML (not input ctx)

Handoff logging (v5):
    Every attempt appends one JSONL line to logs/<ticket_id>-attempts.jsonl:
    {"ts": ..., "attempt": N, "outcome": "pass|fail|error",
     "tokens": N, "elapsed_s": N, "finish": "stop|length|...",
     "budget": N, "tool_calls": N, "reason": "..."}
    This log is the audit trail for parent verification and triage.

Migration note (v6 — STEP-05):
    All ticket dict-access (ticket.get / ticket[key]) has been replaced with
    typed Ticket attribute access (ticket.field). The local load_ticket() now
    delegates to src.ticket_io.load_ticket() and returns a Ticket dataclass.
    Zero raw-dict reads remain in the runner logic paths.
"""

import os
import re
import sys
import glob
import time
import yaml
import json
import subprocess
from pathlib import Path
from openai import OpenAI

from tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
from tools.terminal import run_command

from src.ticket_io import load_ticket as _io_load_ticket
from src.operator_v7 import Ticket

from src.skill_store import match_goal_class, load_skill, write_skill, SkillLoadError, SkillWriteError


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

for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR, IN_PROG_DIR, EXEC_SANDBOX, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# Audit JSONL path for skill cache hits
AUDIT_JSONL = os.path.join(LOG_DIR, "audit.jsonl")

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


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
    """
    Append one JSONL line to logs/<ticket_id>-attempts.jsonl.
    This is the handoff audit trail used by parent verification (TASK-011)
    and by triage when a ticket fails mid-chain.

    Schema (all fields always present):
      ts          ISO-8601 timestamp of attempt completion
      ticket_id   e.g. TASK-008
      attempt     1-indexed retry count
      outcome     pass | fail | error
      tokens      total tokens consumed (prompt + completion)
      elapsed_s   wall-clock seconds for the model call
      tok_s       tokens per second
      finish      model finish_reason (stop | length | content_filter | ...)
      budget      max_tokens requested for this attempt
      tool_calls  number of tool blocks parsed from response
      reason      pass/fail/error detail string
      ram_pre_gb  RAM used before model call
      ram_post_gb RAM used after model call
      cpu_pre_pct CPU % before model call
    """
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
    """Load a YAML ticket and return a fully-populated typed Ticket dataclass.

    Delegates to src.ticket_io.load_ticket() for schema validation, default
    injection, and Ticket.from_dict() construction.  Zero dict-access in
    runner logic paths — callers use ticket.field attribute access only.
    """
    return _io_load_ticket(path)


def save_ticket(path: str, ticket) -> None:
    """Write ticket to YAML. Accepts Ticket dataclass or plain dict (decompose path)."""
    from src.ticket_io import save_ticket as _io_save_ticket
    if isinstance(ticket, Ticket):
        _io_save_ticket(path, ticket)
    else:
        # Raw dict from decompose_goal — write directly
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
    """DFS cycle detection for ticket dependency graph.
    
    Args:
        open_tickets: dict mapping ticket_id to ticket dict with depends_on field
        
    Returns:
        Set of ticket_ids involved in a cycle, or None if no cycle exists
    """
    # Build adjacency list: ticket_id -> list of tickets it depends on
    graph = {}
    for tid, ticket in open_tickets.items():
        deps = ticket.get("depends_on", []) or []
        graph[tid] = [d for d in deps if d in open_tickets]
    
    # DFS with coloring: 0=unvisited, 1=in_stack, 2=completed
    color = {tid: 0 for tid in graph}
    cycle_participants = set()
    
    def dfs(node: str, path: list) -> set | None:
        if node not in color:
            return None  # Not an open ticket (depends on closed/failed)
        
        if color[node] == 1:
            # Found cycle - extract cycle from path
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
    """Check if all consumed artifacts from dependencies are available.
    
    A ticket consumes the produces outputs from its depends_on tickets.
    Returns True if all consumed paths exist (as closed tickets or result files).
    """
    consumes = ticket.consumes or []
    if not consumes:
        return True
    
    # For each consumed path, check if it exists anywhere
    for consumed_path in consumes:
        # Direct file path check
        if os.path.exists(consumed_path):
            continue
        # Closed ticket result file check (look for result files from dependencies)
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
        # Closed ticket check (for tickets without result files)
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


# ── model call ────────────────────────────────────────────────────────────────

def call_model(messages: list, budget: int) -> tuple:
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
                print(f"  [model] attempt {attempt}: empty choices — retry in {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
                continue

            choice = response.choices[0]
            raw    = (choice.message.content or "") if choice.message else ""
            tokens = response.usage.total_tokens if response.usage else 0
            finish = choice.finish_reason or "unknown"

            if not raw.strip():
                print(f"  [model] attempt {attempt}: empty content — retry in {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
                continue

            return raw, tokens, finish, elapsed

        except Exception as e:
            print(f"  [model] attempt {attempt}: {e}")
            if attempt <= MAX_RETRIES:
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


def parse_and_run_tools(response_text: str, exec_timeout: int = 30) -> list:
    results = []
    for match in BLOCK_RE.finditer(normalise(response_text)):
        tool    = match.group(1).strip()
        path    = match.group(2).strip()
        content = match.group(3)
        print(f"  [tool] {tool} → {path}")
        try:
            if tool == "write_file":
                result = REGISTRY.call(tool, {"path": path, "content": content or ""})
            elif tool == "run_command":
                result = REGISTRY.call(tool, {"cmd": path.split()})
            else:
                result = REGISTRY.call(tool, {"path": path})
        except (ToolNotFoundError, ToolArgError) as e:
            result = f"ERROR: {e}"
        result_str = str(result) if isinstance(result, dict) else result
        print(f"  [tool] result: {result_str[:120]}")
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


def build_prompt(ticket: Ticket, upstream_context: str) -> str:
    prompt  = TOOL_SYNTAX
    prompt += f"\nTask: {ticket.task}"
    for cf in (ticket.context_files or []):
        content = tool_read_file(cf)
        prompt += f"\n\n--- {cf} ---\n{content}"
    if upstream_context.strip():
        prompt += f"\n\n--- upstream results ---\n{upstream_context}"
    return prompt


# ── execute one ticket ────────────────────────────────────────────────────────

def execute_ticket(ticket_path: str) -> bool:
    ticket      = load_ticket(ticket_path)
    ticket_id   = ticket.id
    result_path = ticket.result_path or f"{LOG_DIR}/{ticket_id}-result.txt"
    depth       = ticket.depth
    attempt_n   = depth + 1

    print(f"\n[runner] ── {ticket_id} (attempt {attempt_n}) ──")

    # STEP-06-B: Skill cache check
    try:
        if ticket.task:
            goal_class = match_goal_class(ticket.task)
            if goal_class:
                skill = load_skill(goal_class)
                if skill:
                    print(f"[runner] cache hit: {goal_class}")
                    tool_sequence = skill.get("tool_sequence", [])
                    # Execute tool sequence via REGISTRY
                    tool_results = []
                    for tool_call in tool_sequence:
                        tool_name = tool_call.get("tool")
                        tool_args = tool_call.get("args", {})
                        result = REGISTRY.call(tool_name, tool_args)
                        tool_results.append((tool_name, tool_args.get("path", "unknown"), result))
                        print(f"[runner] skill tool: {tool_name} → {tool_args.get('path', 'unknown')}")
                    # Write result file
                    result_str = "\n".join(str(r) for r in tool_results)
                    with open(result_path, "w") as f:
                        f.write(result_str)
                    # Mark ticket as closed
                    from src.operator_v7 import TicketStatus
                    ticket.status = TicketStatus.CLOSED
                    extras = getattr(ticket, "_extras", {})
                    extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    extras["skill_cache_hit"] = True
                    object.__setattr__(ticket, "_extras", extras)
                    # Log to audit JSONL with cache hit
                    audit_entry = {
                        "ticket_id": ticket_id,
                        "goal_class": goal_class,
                        "source": "skill_cache",
                        "cache_hit": True,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                    }
                    with open(AUDIT_JSONL, "a") as f:
                        f.write(json.dumps(audit_entry) + "\n")
                    # Save ticket
                    save_ticket(ticket_path, ticket)
                    # Move to closed
                    closed_path = os.path.join(CLOSED_DIR, f"{ticket_id}.yaml")
                    if ticket_path != closed_path:
                        os.rename(ticket_path, closed_path)
                    print(f"[runner] skill-cached result → {closed_path}")
                    # Write skill to store
                    write_skill(goal_class, tool_sequence)
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
        append_attempt_log(ticket_id, attempt_n, "error", 0, 0.0, "error",
                           budget, 0, str(e), hw_pre, hw_post)
        print(f"  [runner] model call failed: {e}")
        _write_result(result_path, ticket_id, "error", 0, str(e), 0.0,
                      hw_pre, hw_post, [], str(e), raw_full=str(e))
        return False

    hw_post = hw_snap()
    tok_s   = round(tokens / elapsed, 1) if elapsed > 0 else 0
    print(f"  [runner] tokens={tokens}  elapsed={elapsed}s  tok/s={tok_s}  finish={finish}")

    tool_results = parse_and_run_tools(raw, exec_timeout=TIMEOUT)
    passed, reason = _evaluate(result_path, tool_results)
    outcome = "pass" if passed else "fail"

    append_attempt_log(ticket_id, attempt_n, outcome, tokens, elapsed, finish,
                       budget, len(tool_results), reason, hw_pre, hw_post)

    _write_result(result_path, ticket_id, finish, tokens, raw, elapsed,
                  hw_pre, hw_post, tool_results, reason, raw_full=raw)

    if passed:
        ticket.status = __import__("src.operator_v7", fromlist=["TicketStatus"]).TicketStatus.CLOSED
        extras = getattr(ticket, "_extras", {})
        extras["updated_at"]   = time.strftime("%Y-%m-%dT%H:%M:%S")
        extras["attempts_log"] = f"{LOG_DIR}/{ticket_id}-attempts.jsonl"
        object.__setattr__(ticket, "_extras", extras)
        dest = os.path.join(CLOSED_DIR, os.path.basename(ticket_path))
        save_ticket(dest, ticket)
        if os.path.exists(ticket_path):
            os.remove(ticket_path)
        print(f"  [runner] PASS → closed/{os.path.basename(ticket_path)}")
        return True
    else:
        print(f"  [runner] FAIL: {reason}")
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
        t.setdefault("max_depth",     2)
        t.setdefault("created_at",    time.strftime("%Y-%m-%d"))
        t.setdefault("updated_at",    time.strftime("%Y-%m-%d"))
        t.setdefault("result_path",   f"{LOG_DIR}/{tid}-result.txt")
        t.setdefault("context_files", [])
        t.setdefault("rationale",     "")
        t.setdefault("produces",      [])
        t.setdefault("consumes",      [])
        t.setdefault("tags",          [])
        t.setdefault("agent",         MODEL)
        path = os.path.join(OPEN_DIR, f"{tid}.yaml")
        save_ticket(path, t)
        print(f"[runner] ticket → {path}")


# ── drain loop ────────────────────────────────────────────────────────────────

def drain(once: bool = False) -> None:
    max_depth = int(CFG["tickets"].get("decrement_default", 3))

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
            depth  = ticket.depth
            passed = execute_ticket(ticket_path)

            if not passed:
                if depth < max_depth:
                    ticket.depth = depth + 1
                    extras = getattr(ticket, "_extras", {})
                    extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    object.__setattr__(ticket, "_extras", extras)
                    save_ticket(ticket_path, ticket)
                    print(f"[runner] retry queued depth={depth+1}: {ticket_id}")
                else:
                    fail_path = os.path.join(FAIL_DIR, os.path.basename(ticket_path))
                    from src.operator_v7 import TicketStatus
                    ticket.status = TicketStatus.ESCALATED
                    extras = getattr(ticket, "_extras", {})
                    extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    object.__setattr__(ticket, "_extras", extras)
                    save_ticket(fail_path, ticket)
                    if os.path.exists(ticket_path):
                        os.remove(ticket_path)
                    print(f"[runner] max_depth reached → failed/{os.path.basename(ticket_path)}")

            if once:
                return

        if dispatched_this_pass == 0 and deferred:
            # STEP-08-C: Check for deadlock cycles before giving up
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
                        fail_path = os.path.join(FAIL_DIR, os.path.basename(p))
                        from src.operator_v7 import TicketStatus
                        ticket.status = TicketStatus.ESCALATED
                        extras = getattr(ticket, "_extras", {})
                        extras["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        extras["deadlock_reason"] = "cycle"
                        extras["cycle_participants"] = list(cycle)
                        object.__setattr__(ticket, "_extras", extras)
                        save_ticket(fail_path, ticket)
                        if os.path.exists(p):
                            os.remove(p)
                        print(f"[runner] cycle participant → failed/{os.path.basename(p)}")
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
    once       = "--once"       in sys.argv
    no_prewarm = "--no-prewarm" in sys.argv

    if not no_prewarm:
        prewarm()

    goal = None
    for i, arg in enumerate(sys.argv):
        if arg == "--goal" and i + 1 < len(sys.argv):
            goal = sys.argv[i + 1]
            break

    if goal:
        print(f"[runner] goal: {goal}")
        existing_nums = []
        for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR]:
            for p in glob.glob(os.path.join(d, "TASK-*.yaml")):
                stem = Path(p).stem
                try:
                    existing_nums.append(int(stem.split("-")[1]))
                except (IndexError, ValueError):
                    pass
        first_n = max(existing_nums, default=0) + 1
        tickets = decompose_goal(goal, first_n)
        if not tickets:
            print("[runner] decomposition produced no tickets — abort")
            sys.exit(1)
        write_tickets(tickets)
        print(f"[runner] {len(tickets)} ticket(s) written")

    drain(once=once)


if __name__ == "__main__":
    main()
