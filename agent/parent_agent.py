#!/usr/bin/env python3
"""
parent_agent.py — Fractal Claws parent agent.

Usage:
    python agent/parent_agent.py                        # dispatch all open tickets
    python agent/parent_agent.py --once                 # dispatch one ticket then exit
    python agent/parent_agent.py --goal "<goal>"        # A3B decomposes goal into tickets

Model roles:
    DECOMPOSE_MODEL  Qwen3.5-35B-A3B-GGUF  — goal decomposition (parent)
    CHILD_MODEL      Qwen3.5-4B-GGUF       — ticket execution (child)

Both models are pre-warmed at startup to prevent Lemonade slot eviction.
"""
import sys
import os
import re
import time
import subprocess
import glob
import yaml
from openai import OpenAI

CHILD             = os.path.join(os.path.dirname(__file__), "child_agent.py")
OPEN_DIR          = "tickets/open"
CLOSED_DIR        = "tickets/closed"
FAIL_DIR          = "tickets/failed"
DEFAULT_MAX_DEPTH = 1

ENDPOINT          = "http://localhost:8000/api/v1"
API_KEY           = "x"
DECOMPOSE_MODEL   = "Qwen3.5-35B-A3B-GGUF"
CHILD_MODEL       = "Qwen3.5-4B-GGUF"

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


# ────────────────────────────── pre-warm
PREWARM_MODELS = [DECOMPOSE_MODEL, CHILD_MODEL]

def prewarm_models():
    """
    Send a 1-token completion to each model at startup.
    Forces Lemonade to load both into unified RAM before any real work,
    preventing mid-dispatch slot eviction and RAM swap.
    """
    print("[parent] pre-warming models...")
    for model in PREWARM_MODELS:
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
                timeout=60,
            )
            print(f"[parent] warm OK: {model}")
        except Exception as e:
            print(f"[parent] warm FAILED: {model} — {e}")
    print("[parent] pre-warm done")


# ────────────────────────────── ticket helpers
def load_ticket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0]


def save_ticket(path: str, ticket: dict):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


def deps_met(ticket: dict) -> bool:
    deps = ticket.get("depends_on", []) or []
    for dep in deps:
        if not os.path.exists(os.path.join(CLOSED_DIR, f"{dep}.yaml")):
            return False
    return True


def evaluate_result(result_path: str) -> tuple:
    if not os.path.exists(result_path):
        return False, "result file missing"
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content or content == "NO RESPONSE":
        return False, "result empty or NO RESPONSE"
    if re.search(r'^ERROR:', content, re.MULTILINE):
        return False, "result contains ERROR"
    rc_match = re.search(r'returncode:\s*(\d+)', content)
    if rc_match and rc_match.group(1) != "0":
        return False, f"non-zero returncode: {rc_match.group(1)}"
    return True, "ok"


def dispatch(ticket_path: str) -> int:
    result = subprocess.run([sys.executable, CHILD, ticket_path], capture_output=False)
    return result.returncode


def make_retry_ticket(ticket: dict, reason: str) -> dict:
    retry = dict(ticket)
    depth = int(retry.get("depth", 0)) + 1
    retry["depth"]      = depth
    retry["status"]     = "open"
    retry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    audit    = retry.get("audit", {}) or {}
    attempts = audit.get("attempts", []) or []
    attempts.append({"depth": depth - 1, "fail_reason": reason, "ts": retry["updated_at"]})
    audit["attempts"] = attempts
    retry["audit"] = audit
    return retry


def scan_open() -> list:
    return sorted(glob.glob(os.path.join(OPEN_DIR, "*.yaml")))


def next_ticket_id() -> str:
    existing = []
    for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR]:
        for p in glob.glob(os.path.join(d, "TASK-*.yaml")):
            base = os.path.basename(p).replace(".yaml", "")
            try:
                existing.append(int(base.split("-")[1]))
            except (IndexError, ValueError):
                pass
    return f"TASK-{max(existing, default=0) + 1:03d}"


# ────────────────────────────── A3B goal decomposition
DECOMPOSE_SYSTEM = """\
You are a task decomposer for an autonomous agent system.
Given a plain-English goal, output a YAML list of atomic tickets.

Rules:
- Each ticket must be completable in 1-2 tool calls.
- Available tools per ticket: write_file, exec_python, read_file.
- exec_python paths must be inside output/
- CRITICAL: write_file MUST appear before exec_python when writing and running the same file.
- Use depends_on to express sequential dependencies between tickets.
- Output ONLY valid YAML. No prose, no markdown fences, no explanation.
- Be concise — use minimal tokens per ticket field.

Output format:
- ticket_id: TASK-NNN
  title: <short title>
  task: >-
    <single sentence: what to do, what file to write, what to run>
  depends_on: []
  allowed_tools:
    - name: write_file
    - name: exec_python
"""


def decompose_goal(goal: str, first_id_n: int) -> list:
    print(f"[parent] calling A3B to decompose goal...")
    user_prompt = (
        f"Goal: {goal}\n\n"
        f"Start ticket numbering from TASK-{first_id_n:03d}.\n"
        f"Output ONLY the YAML list. No extra text."
    )
    response = client.chat.completions.create(
        model=DECOMPOSE_MODEL,
        messages=[
            {"role": "system", "content": DECOMPOSE_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=4096,
        temperature=0.1,
        timeout=180,
    )
    raw  = response.choices[0].message.content or ""
    used = response.usage.total_tokens if response.usage else 0
    print(f"[parent] A3B responded ({used} tokens)")
    print(f"[parent] A3B raw:\n{raw[:2000]}")

    cleaned = re.sub(r'^```[\w]*\n?', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'```$', '', cleaned.strip())
    try:
        tickets = yaml.safe_load(cleaned)
        if not isinstance(tickets, list):
            print(f"[parent] ERROR: A3B output not a list, got {type(tickets)}")
            return []
        return tickets
    except yaml.YAMLError as e:
        print(f"[parent] ERROR: failed to parse A3B YAML: {e}")
        print(f"[parent] raw output was:\n{raw}")
        return []


def write_decomposed_tickets(tickets: list) -> list:
    os.makedirs(OPEN_DIR, exist_ok=True)
    written = []
    for t in tickets:
        tid = t.get("ticket_id", next_ticket_id())
        t.setdefault("status",          "open")
        t.setdefault("depth",           0)
        t.setdefault("max_depth",       1)
        t.setdefault("created_at",      time.strftime("%Y-%m-%d"))
        t.setdefault("updated_at",      time.strftime("%Y-%m-%d"))
        t.setdefault("result_path",     f"logs/{tid}-result.txt")
        t.setdefault("max_tokens",      512)
        t.setdefault("timeout_seconds", 60)
        t.setdefault("context_files",   [])
        path = os.path.join(OPEN_DIR, f"{tid}.yaml")
        save_ticket(path, t)
        print(f"[parent] wrote ticket: {path}")
        written.append(path)
    return written


# ────────────────────────────── main
def main():
    once = "--once" in sys.argv
    os.makedirs(OPEN_DIR,   exist_ok=True)
    os.makedirs(FAIL_DIR,   exist_ok=True)
    os.makedirs(CLOSED_DIR, exist_ok=True)

    # ── pre-warm both models before any dispatch
    prewarm_models()

    # ── --goal mode
    goal = None
    for i, arg in enumerate(sys.argv):
        if arg == "--goal" and i + 1 < len(sys.argv):
            goal = sys.argv[i + 1]
            break

    if goal:
        print(f"[parent] goal: {goal}")
        first_n = max(
            [int(os.path.basename(p).replace(".yaml", "").split("-")[1])
             for d in [OPEN_DIR, CLOSED_DIR, FAIL_DIR]
             for p in glob.glob(os.path.join(d, "TASK-*.yaml"))
             if os.path.basename(p).replace(".yaml", "").split("-")[1].isdigit()],
            default=0
        ) + 1
        tickets = decompose_goal(goal, first_n)
        if not tickets:
            print("[parent] ERROR: decomposition produced no tickets. Aborting.")
            sys.exit(1)
        write_decomposed_tickets(tickets)
        print(f"[parent] decomposed into {len(tickets)} ticket(s), dispatching...")

    # ── dispatch loop
    ticket_paths = scan_open()
    if not ticket_paths:
        print("[parent] no open tickets")
        return

    deferred = []

    for ticket_path in ticket_paths:
        ticket_id = os.path.basename(ticket_path).replace(".yaml", "")
        ticket    = load_ticket(ticket_path)

        if not deps_met(ticket):
            unmet = [d for d in (ticket.get("depends_on") or [])
                     if not os.path.exists(os.path.join(CLOSED_DIR, f"{d}.yaml"))]
            print(f"[parent] DEFERRED {ticket_id} — waiting on: {unmet}")
            deferred.append(ticket_path)
            continue

        print(f"\n[parent] === dispatching {ticket_id} ===")
        depth     = int(ticket.get("depth", 0))
        max_depth = int(ticket.get("max_depth", DEFAULT_MAX_DEPTH))

        rc = dispatch(ticket_path)
        print(f"[parent] child exited: {rc}")

        result_path = ticket.get("result_path", f"logs/{ticket_id}-result.txt")
        passed, reason = evaluate_result(result_path)

        if passed:
            print(f"[parent] PASS: {ticket_id}")
        else:
            print(f"[parent] FAIL: {ticket_id} — {reason}")
            if depth < max_depth:
                retry = make_retry_ticket(ticket, reason)
                retry_path = os.path.join(OPEN_DIR, os.path.basename(ticket_path))
                save_ticket(retry_path, retry)
                print(f"[parent] retry queued (depth {retry['depth']}): {retry_path}")
            else:
                fail_path = os.path.join(FAIL_DIR, os.path.basename(ticket_path))
                ticket["status"]     = "failed"
                ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                save_ticket(fail_path, ticket)
                print(f"[parent] max depth reached — moved to failed/: {fail_path}")

        if once:
            break

    if deferred:
        print(f"\n[parent] {len(deferred)} ticket(s) deferred (unmet deps): "
              f"{[os.path.basename(p) for p in deferred]}")

    print("\n[parent] done")


if __name__ == "__main__":
    main()
