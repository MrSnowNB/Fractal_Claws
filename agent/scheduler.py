#!/usr/bin/env python3
"""
scheduler.py — DAG-aware ticket picker for Fractal Claws.

Ported from MUMPS_Bot/agent/scheduler.py.

Usage (standalone):
    python agent/scheduler.py           # print next ready ticket
    python agent/scheduler.py --all     # print full ready queue
    python agent/scheduler.py --status  # print counts per state
"""

from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent


def load_tickets(directory: Path) -> list[dict]:
    tickets = []
    for p in sorted(directory.glob("*.yaml")):
        try:
            raw = p.read_text().strip()
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                data["_path"] = p
                tickets.append(data)
        except Exception:
            pass
    return tickets


def closed_ids() -> set:
    closed_dir = ROOT / "tickets" / "closed"
    return {p.stem for p in closed_dir.glob("*.yaml")}


def ready_tickets() -> list[dict]:
    open_dir = ROOT / "tickets" / "open"
    done = closed_ids()
    ready = []
    for t in load_tickets(open_dir):
        deps = t.get("depends_on") or []
        status = t.get("status", "open")
        if status in ("open", "pending") and all(d in done for d in deps):
            ready.append(t)
    return ready


def status_counts() -> dict:
    counts = {}
    for state in ["open", "in_progress", "closed", "failed"]:
        d = ROOT / "tickets" / state
        counts[state] = len(list(d.glob("*.yaml"))) if d.exists() else 0
    return counts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fractal Claws ticket scheduler")
    parser.add_argument("--all", action="store_true", help="Show all ready tickets")
    parser.add_argument("--status", action="store_true", help="Show ticket counts per state")
    args = parser.parse_args()

    if args.status:
        for state, count in status_counts().items():
            print(f"{state:<15} {count}")
    elif args.all:
        for t in ready_tickets():
            tid = t.get("ticket_id", t.get("id", "?"))
            print(f"{tid:<12} {t.get('title', '')}")
    else:
        ready = ready_tickets()
        if ready:
            t = ready[0]
            tid = t.get("ticket_id", t.get("id", "?"))
            print(f"{tid} — {t.get('title', '')}")
        else:
            print("No ready tickets.")
