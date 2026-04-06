#!/usr/bin/env python3
"""
parent_agent.py — Fractal Claws parent agent.

Usage:
    python agent/parent_agent.py [--once]
    python agent/parent_agent.py --goal "<plain English goal>"  (A3B decompose — Phase 2)

Scans tickets/open/ for YAML tickets, respects depends_on DAG ordering,
dispatches each to child_agent.py, reads the result log, marks PASS/FAIL.

Depends-on logic:
  Before dispatching a ticket, all ticket_ids listed in depends_on must
  already exist as closed tickets in tickets/closed/.
  Tickets whose deps are unmet are skipped and re-queued each pass.

Options:
  --once    Process one ready ticket then exit

Result evaluation:
  PASS  — result log exists, non-empty, no ERROR lines, returncode 0 if present
  FAIL  — result log missing, empty, contains ERROR, or non-zero returncode

On FAIL the parent writes a retry ticket with depth+1.
max_depth per ticket is read from the ticket itself (default 1, locked).
"""
import sys
import os
import re
import time
import subprocess
import glob
import yaml

CHILD      = os.path.join(os.path.dirname(__file__), "child_agent.py")
OPEN_DIR   = "tickets/open"
CLOSED_DIR = "tickets/closed"
FAIL_DIR   = "tickets/failed"
DEFAULT_MAX_DEPTH = 1   # locked — increase only after stability gate


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
    """Return True if all depends_on tickets are present in tickets/closed/."""
    deps = ticket.get("depends_on", []) or []
    for dep in deps:
        closed_path = os.path.join(CLOSED_DIR, f"{dep}.yaml")
        if not os.path.exists(closed_path):
            return False
    return True


def evaluate_result(result_path: str) -> tuple:
    """
    Returns (passed: bool, reason: str)
    PASS if: file exists, non-empty, no ERROR lines, returncode 0 if present.
    """
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
    """Run child_agent.py on ticket. Returns subprocess returncode."""
    result = subprocess.run(
        [sys.executable, CHILD, ticket_path],
        capture_output=False
    )
    return result.returncode


def make_retry_ticket(ticket: dict, reason: str) -> dict:
    """Clone ticket with incremented depth for retry."""
    retry = dict(ticket)
    depth = int(retry.get("depth", 0)) + 1
    retry["depth"]      = depth
    retry["status"]     = "open"
    retry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    audit = retry.get("audit", {}) or {}
    attempts = audit.get("attempts", []) or []
    attempts.append({"depth": depth - 1, "fail_reason": reason, "ts": retry["updated_at"]})
    audit["attempts"] = attempts
    retry["audit"] = audit
    return retry


def scan_open() -> list:
    return sorted(glob.glob(os.path.join(OPEN_DIR, "*.yaml")))


def main():
    once = "--once" in sys.argv
    os.makedirs(OPEN_DIR, exist_ok=True)
    os.makedirs(FAIL_DIR, exist_ok=True)
    os.makedirs(CLOSED_DIR, exist_ok=True)

    tickets = scan_open()
    if not tickets:
        print("[parent] no open tickets")
        return

    deferred = []  # tickets whose deps were unmet this pass

    for ticket_path in tickets:
        ticket_id = os.path.basename(ticket_path).replace(".yaml", "")
        ticket    = load_ticket(ticket_path)

        # ── depends_on guard ──────────────────────────────────────────
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
        print(f"\n[parent] {len(deferred)} ticket(s) deferred (unmet deps): {[os.path.basename(p) for p in deferred]}")

    print("\n[parent] done")


if __name__ == "__main__":
    main()
