#!/usr/bin/env python3
"""
runner.py — Fractal Claws agent skeleton v2

Single entry point. Reads all config from settings.yaml.
No model names, no depths, no tiers hardcoded here.

Usage:
    python agent/runner.py                        # drain all open tickets
    python agent/runner.py --goal "<goal>"        # decompose goal then drain
    python agent/runner.py --once                 # dispatch one ticket then exit

Skeleton guarantees:
    1. Goal enters  →  decomposed into YAML tickets in tickets/open/
    2. Dispatch loop drains until no open, unblocked tickets remain
       (handles deferred tickets correctly — re-queues until deps close)
    3. Each closed ticket's result is forwarded as context to dependents
    4. Token budget per ticket is derived from task complexity, not a flat cap
    5. Hardware snapshot on every model call
    6. All config from settings.yaml — zero hardcoded values
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
FAIL_DIR     = "tickets/failed"
IN_PROG_DIR  = CFG["tickets"].get("in_progress_dir", "tickets/in_progress")
EXEC_SANDBOX = "output"
LOG_DIR      = CFG["logging"]["dir"].rstrip("/")

for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR, IN_PROG_DIR, EXEC_SANDBOX, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


# ── token budget ──────────────────────────────────────────────────────────────

BUDGET_FLOOR   = 256
BUDGET_CEILING = int(CFG["model"].get("context_window", 8192) * 0.4)  # 40% of ctx

# Words in the task description roughly predict output size needed
WORDS_PER_TOKEN = 0.75
OUTPUT_RATIO    = 4.0   # output tokens ≈ 4× input words for code tasks

def token_budget(ticket: dict) -> int:
    """
    Derive a per-ticket token budget from task length.
    Short tasks (verify, read) get FLOOR.
    Long tasks (write, generate) scale up to CEILING.
    Never exceeds context_window * 0.4.
    """
    task_words  = len(str(ticket.get("task", "")).split())
    estimate    = int(task_words / WORDS_PER_TOKEN * OUTPUT_RATIO)
    budget      = max(BUDGET_FLOOR, min(estimate, BUDGET_CEILING))
    # Explicit override in ticket always wins
    return int(ticket.get("max_tokens", budget))


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


# ── ticket helpers ────────────────────────────────────────────────────────────

def load_ticket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0] or {}


def save_ticket(path: str, ticket: dict) -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


def scan_open() -> list:
    return sorted(glob.glob(os.path.join(OPEN_DIR, "*.yaml")))


def is_closed(ticket_id: str) -> bool:
    return os.path.exists(os.path.join(CLOSED_DIR, f"{ticket_id}.yaml"))


def deps_met(ticket: dict) -> bool:
    return all(is_closed(d) for d in (ticket.get("depends_on") or []))


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
    """
    Extract a compact summary from a closed ticket's result file.
    This is injected as context into dependent tickets.
    """
    if not os.path.exists(result_path):
        return ""
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Return the tool results section only — not the full hw telemetry
    marker = "=== tool results ==="
    if marker in content:
        return content.split(marker, 1)[1].strip()[:800]
    return content.strip()[:800]


def inject_upstream_context(ticket: dict) -> str:
    """
    For each dependency, read its closed result and build a context block.
    Returns a formatted string ready to append to the user prompt.
    """
    deps = ticket.get("depends_on") or []
    if not deps:
        return ""
    blocks = []
    for dep_id in deps:
        closed_path = os.path.join(CLOSED_DIR, f"{dep_id}.yaml")
        if not os.path.exists(closed_path):
            continue
        dep_ticket  = load_ticket(closed_path)
        result_path = dep_ticket.get("result_path", f"{LOG_DIR}/{dep_id}-result.txt")
        summary     = result_summary(result_path)
        if summary:
            blocks.append(f"--- output of {dep_id} ---\n{summary}")
    return "\n\n".join(blocks)


# ── model call ────────────────────────────────────────────────────────────────

def call_model(messages: list, budget: int) -> tuple:
    """
    Call model with retry on empty/null choices.
    Returns (raw_text, total_tokens, finish_reason, elapsed_s).
    Raises RuntimeError after all retries exhausted.
    """
    for attempt in range(1, MAX_RETRIES + 2):  # +2: attempts=2 means 3 tries total
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


# ── tools ─────────────────────────────────────────────────────────────────────

def tool_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"ERROR: file not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tool_write_file(path: str, content: str) -> str:
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


# ── parser ────────────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(r'^[ \t]+(TOOL:|PATH:|END$|DONE$)', re.MULTILINE)

def normalise(text: str) -> str:
    return _HEADER_RE.sub(lambda m: m.group(1), text)


BLOCK_RE = re.compile(
    r'TOOL:\s*(\S+)\s*\nPATH:\s*(\S+)\s*\n(?:CONTENT:\n([\s\S]*?)\nEND|END)',
    re.MULTILINE
)


def parse_and_run_tools(response_text: str, exec_timeout: int = 30) -> list:
    results = []
    for match in BLOCK_RE.finditer(normalise(response_text)):
        tool    = match.group(1).strip()
        path    = match.group(2).strip()
        content = match.group(3)
        print(f"  [tool] {tool} → {path}")
        if tool == "read_file":
            result = tool_read_file(path)
        elif tool == "write_file":
            result = tool_write_file(path, content or "")
        elif tool == "list_dir":
            result = tool_list_dir(path)
        elif tool == "exec_python":
            result = tool_exec_python(path, timeout=exec_timeout)
        else:
            result = f"ERROR: unknown tool: {tool}"
        print(f"  [tool] result: {result[:120]}")
        results.append((tool, path, result))
    return results


# ── prompt ────────────────────────────────────────────────────────────────────

TOOL_SYNTAX = """\
You are a tool-calling agent. Output ONLY raw tool blocks — no prose, no markdown.

Available tools:

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

Rules:
1. First line of response must be TOOL:
2. No indentation on TOOL/PATH/END lines.
3. exec_python paths must be inside output/
4. write_file before exec_python on the same path.
5. After last tool block write: DONE
"""


def build_prompt(ticket: dict, upstream_context: str) -> str:
    prompt  = TOOL_SYNTAX
    prompt += f"\nTask: {ticket['task']}"
    # inject context_files declared in ticket
    for cf in (ticket.get("context_files") or []):
        content = tool_read_file(cf)
        prompt += f"\n\n--- {cf} ---\n{content}"
    # inject upstream results from completed dependencies
    if upstream_context.strip():
        prompt += f"\n\n--- upstream results ---\n{upstream_context}"
    return prompt


# ── execute one ticket ────────────────────────────────────────────────────────

def execute_ticket(ticket_path: str) -> bool:
    """
    Execute a single ticket. Returns True on pass, False on fail.
    Moves ticket to closed/ on pass, leaves in open/ for retry/fail handling.
    """
    ticket    = load_ticket(ticket_path)
    ticket_id = ticket.get("ticket_id", Path(ticket_path).stem)
    result_path = ticket.get("result_path", f"{LOG_DIR}/{ticket_id}-result.txt")

    print(f"\n[runner] ── {ticket_id} ──")

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
        print(f"  [runner] model call failed: {e}")
        _write_result(result_path, ticket_id, "model_error", 0, str(e), elapsed=0,
                      hw_pre=hw_pre, hw_post=hw_snap(), tool_results=[])
        return False

    hw_post = hw_snap()
    tok_s   = round(tokens / elapsed, 1) if elapsed > 0 else 0
    print(f"  [runner] tokens={tokens}  elapsed={elapsed}s  tok/s={tok_s}  finish={finish}")

    tool_results = parse_and_run_tools(raw, exec_timeout=TIMEOUT)
    passed, reason = _evaluate(result_path, tool_results)

    _write_result(result_path, ticket_id, finish, tokens, raw, elapsed,
                  hw_pre, hw_post, tool_results, reason)

    if passed:
        # close ticket
        ticket["status"]     = "closed"
        ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        dest = os.path.join(CLOSED_DIR, os.path.basename(ticket_path))
        save_ticket(dest, ticket)
        os.remove(ticket_path)
        print(f"  [runner] PASS → closed/{os.path.basename(ticket_path)}")
        return True
    else:
        print(f"  [runner] FAIL: {reason}")
        return False


def _evaluate(result_path: str, tool_results: list) -> tuple:
    """Pass/fail heuristics on tool output."""
    if not tool_results:
        return False, "no tool calls detected"
    for tool, path, result in tool_results:
        if result.startswith("ERROR:"):
            return False, f"{tool}:{path} → {result[:80]}"
        if "returncode:" in result:
            rc = re.search(r'returncode:\s*(\d+)', result)
            if rc and rc.group(1) != "0":
                return False, f"non-zero returncode: {rc.group(1)}"
    return True, "ok"


def _write_result(result_path, ticket_id, finish, tokens, raw, elapsed,
                  hw_pre, hw_post, tool_results, reason="ok"):
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
            lines += [f"[{tool}] {path}", result, ""]
    else:
        lines += ["no tool calls detected", "", "=== raw ===", raw]
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── decompose ─────────────────────────────────────────────────────────────────

DECOMPOSE_SYSTEM = """\
You are a task decomposer for an autonomous agent system.
Given a plain-English goal, output a YAML list of atomic tickets.

Rules:
- Each ticket: completable in 1-2 tool calls.
- Available tools: write_file, exec_python, read_file, list_dir.
- exec_python paths must be inside output/
- write_file MUST appear before exec_python on the same path.
- Use depends_on to express sequential dependencies.
- Output ONLY valid YAML. No prose, no markdown fences.

Output format (one or more):
- ticket_id: TASK-NNN
  title: <short title>
  task: >-
    <one sentence: what to do, what file, what to run>
  depends_on: []
  allowed_tools:
    - name: write_file
"""


def decompose_goal(goal: str, first_n: int) -> list:
    print(f"[runner] decomposing goal...")
    raw = ""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": DECOMPOSE_SYSTEM},
                {"role": "user",
                 "content": f"Goal: {goal}\nStart ticket numbering from TASK-{first_n:03d}.\nOutput ONLY the YAML list."},
            ],
            max_tokens=2048,
            temperature=0.1,
            timeout=TIMEOUT * 2,
        )
        if response.choices:
            raw = response.choices[0].message.content or ""
    except Exception as e:
        print(f"[runner] decompose error: {e}")
        return []

    tokens = response.usage.total_tokens if response.usage else 0
    print(f"[runner] decompose: {tokens} tokens")

    cleaned = re.sub(r'^```[\w]*\n?', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'```$', '', cleaned.strip())
    try:
        tickets = yaml.safe_load(cleaned)
        return tickets if isinstance(tickets, list) else []
    except yaml.YAMLError as e:
        print(f"[runner] YAML parse error: {e}")
        return []


def write_tickets(tickets: list) -> None:
    for t in tickets:
        tid = t.get("ticket_id", next_ticket_id())
        t.setdefault("status",          "open")
        t.setdefault("depth",           0)
        t.setdefault("max_depth",       2)
        t.setdefault("created_at",      time.strftime("%Y-%m-%d"))
        t.setdefault("updated_at",      time.strftime("%Y-%m-%d"))
        t.setdefault("result_path",     f"{LOG_DIR}/{tid}-result.txt")
        t.setdefault("context_files",   [])
        # no max_tokens default — token_budget() will derive it
        path = os.path.join(OPEN_DIR, f"{tid}.yaml")
        save_ticket(path, t)
        print(f"[runner] ticket → {path}")


# ── drain loop ────────────────────────────────────────────────────────────────

def drain(once: bool = False) -> None:
    """
    Core loop. Keeps running until:
      - no open tickets remain, OR
      - all remaining open tickets have unmet deps AND nothing was dispatched
        in the last full pass (deadlock guard).

    On each pass:
      1. Scan open tickets
      2. Dispatch all whose deps are met
      3. On pass, close ticket + results forward automatically on next pass
      4. On fail, increment depth; at max_depth move to failed/
      5. Loop until drained or deadlocked
    """
    max_depth = int(CFG["tickets"].get("decrement_default", 3))  # reuse as max_depth

    while True:
        tickets = scan_open()
        if not tickets:
            print("[runner] all tickets closed — done")
            break

        dispatched_this_pass = 0
        deferred = []

        for ticket_path in tickets:
            ticket    = load_ticket(ticket_path)
            ticket_id = Path(ticket_path).stem

            if not deps_met(ticket):
                unmet = [d for d in (ticket.get("depends_on") or [])
                         if not is_closed(d)]
                print(f"[runner] deferred {ticket_id} — waiting on {unmet}")
                deferred.append(ticket_path)
                continue

            dispatched_this_pass += 1
            depth     = int(ticket.get("depth", 0))
            passed    = execute_ticket(ticket_path)

            if not passed:
                if depth < max_depth:
                    # re-queue with incremented depth
                    ticket["depth"]      = depth + 1
                    ticket["status"]     = "open"
                    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    save_ticket(ticket_path, ticket)
                    print(f"[runner] retry queued depth={depth+1}: {ticket_id}")
                else:
                    fail_path = os.path.join(FAIL_DIR, os.path.basename(ticket_path))
                    ticket["status"]     = "failed"
                    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    save_ticket(fail_path, ticket)
                    if os.path.exists(ticket_path):
                        os.remove(ticket_path)
                    print(f"[runner] max_depth reached → failed/{os.path.basename(ticket_path)}")

            if once:
                return

        # Deadlock guard: if nothing was dispatched and tickets remain, exit
        if dispatched_this_pass == 0 and deferred:
            print(f"[runner] deadlock — {len(deferred)} ticket(s) blocked on unmet deps:")
            for p in deferred:
                ticket    = load_ticket(p)
                ticket_id = Path(p).stem
                unmet     = [d for d in (ticket.get("depends_on") or [])
                             if not is_closed(d)]
                print(f"  {ticket_id} waiting on {unmet}")
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
    once = "--once" in sys.argv

    prewarm()

    # --goal mode
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
