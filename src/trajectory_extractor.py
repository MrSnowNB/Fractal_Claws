#!/usr/bin/env python3
"""
trajectory_extractor.py — Self-improvement loop for Cline

Reads closed tickets, extracts winning trajectories from attempts logs,
and writes skill YAML files for reuse.
"""

import os
import re
import glob
import json
import yaml
from pathlib import Path


# ── module-level constants ──────────────────────────────────────────────────────

LOG_DIR    = "logs"
SKILLS_DIR = "skills"
CLOSED_DIR = "tickets/closed"


# ── helper ──────────────────────────────────────────────────────────────────────

def _load_ticket(path: str) -> dict:
    """Handle single and multi-doc YAML (same as runner.py load_ticket)."""
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0] or {}


# ── core functions ──────────────────────────────────────────────────────────────

def extract_trajectory(ticket_id: str, log_dir: str | None = None) -> dict | None:
    """
    Read <log_dir>/<ticket_id>-attempts.jsonl.
    Return first record where outcome == "pass".
    Return None if file missing or no pass.
    Skip malformed JSON lines silently.
    """
    if log_dir is None:
        log_dir = LOG_DIR
    log_path = os.path.join(log_dir, f"{ticket_id}-attempts.jsonl")
    print(f"[DEBUG] extract_trajectory: ticket_id={ticket_id}, log_dir={log_dir}, log_path={log_path}")
    if not os.path.exists(log_path):
        print(f"[DEBUG] extract_trajectory: file not found: {log_path}")
        return None

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                print(f"[DEBUG] extract_trajectory: record={record}")
                if record.get("outcome") == "pass":
                    return record
            except json.JSONDecodeError:
                continue

    print(f"[DEBUG] extract_trajectory: no pass found in {log_path}")
    return None


def goal_class(ticket: dict) -> str:
    """
    If ticket has tags list: join first 3 tags with "-", lowercase, spaces→dashes.
    Else: slugify ticket["title"] or ticket["ticket_id"].
    Max length 48 chars.
    Returns a lowercase hyphenated string.
    """
    tags = ticket.get("tags", [])
    if tags:
        first_three = tags[:3]
        joined = " ".join(first_three)
        slug = joined.lower().replace(" ", "-")
    else:
        title = ticket.get("title", ticket.get("ticket_id", ""))
        slug = title.lower().replace(" ", "-")

    # Remove any non-alphanumeric/hyphen characters
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip trailing hyphen
    slug = slug.rstrip("-")

    return slug[:48]


def write_skill(goal_cls: str, trajectory: dict, ticket: dict, skills_dir: str = SKILLS_DIR) -> str:
    """
    Create skills/ dir if needed.
    Write skills/<goal_cls>.yaml with required keys.
    If file exists and existing elapsed_s <= new elapsed_s: skip (keep best).
    Return the path written.
    """
    os.makedirs(skills_dir, exist_ok=True)
    path = os.path.join(skills_dir, f"{goal_cls}.yaml")

    # Check if file exists and has better or equal elapsed_s
    if os.path.exists(path):
        existing = _load_ticket(path)
        # Check if existing has elapsed_s and it's <= new
        if isinstance(existing, dict) and "elapsed_s" in existing:
            if existing["elapsed_s"] <= trajectory.get("elapsed_s", float("inf")):
                return path  # Keep existing (skip write)

    skill = {
        "goal_class": goal_cls,
        "ticket_id": ticket.get("ticket_id", ""),
        "tags": ticket.get("tags", []),
        "tool_calls": trajectory.get("tool_calls", 0),
        "tokens": trajectory.get("tokens", 0),
        "elapsed_s": trajectory.get("elapsed_s", 0),
        "tok_s": trajectory.get("tok_s", 0),
        "finish": trajectory.get("finish", ""),
        "attempt": trajectory.get("attempt", 1),
        "ts": trajectory.get("ts", ""),
        "produces": ticket.get("produces", []),
        "consumes": ticket.get("consumes", []),
    }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(skill, f, allow_unicode=True, sort_keys=False)

    return path


def run_extraction(closed_dir: str | None = None, log_dir: str | None = None, skills_dir: str | None = None) -> list[str]:
    """
    Globs tickets/closed/*.yaml (or closed_dir).
    For each ticket: extract_trajectory, goal_class, write_skill.
    Skip tickets with no pass trajectory.
    Return list of skill paths written.
    Print "[trajectory] <ticket_id> → <path>" for each.
    """
    if closed_dir is None:
        closed_dir = CLOSED_DIR
    patterns = os.path.join(closed_dir, "*.yaml")
    ticket_paths = sorted(glob.glob(patterns))
    print(f"[DEBUG] closed_dir={closed_dir}, patterns={patterns}, ticket_paths={ticket_paths}")

    paths_written = []

    for tp in ticket_paths:
        print(f"[DEBUG] loading ticket: {tp}")
        ticket = _load_ticket(tp)
        print(f"[DEBUG] ticket={ticket}")
        ticket_id = ticket.get("ticket_id", Path(tp).stem)
        print(f"[DEBUG] ticket_id={ticket_id}")

        trajectory = extract_trajectory(ticket_id, log_dir=log_dir)
        print(f"[DEBUG] trajectory={trajectory}")
        if trajectory is None:
            print(f"[DEBUG] skipping: no trajectory found for {ticket_id}")
            continue

        gcls = goal_class(ticket)
        skill_path = write_skill(gcls, trajectory, ticket, skills_dir=skills_dir)

        paths_written.append(skill_path)
        print(f"[trajectory] {ticket_id} → {skill_path}")

    return paths_written


# ── CLI ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    paths = run_extraction()
    print(f"[trajectory] extracted {len(paths)} skill(s)")
    for p in paths:
        print(f"  {p}")