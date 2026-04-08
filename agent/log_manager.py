#!/usr/bin/env python3
"""
log_manager.py — FIFO retention policy for logs/

Evicts oldest -attempts.jsonl / -result.txt pairs when log count exceeds
max_on_disk. Never evicts escalated tickets (those in tickets/failed/).

Called from:
  - runner.drain()       — at drain entry, before any tickets execute
  - execute_ticket()     — after every PASS close

Settings keys (all in settings.yaml under logging:):
  max_logs:        int  — max -attempts.jsonl files on disk (default 100)
  min_retain:      int  — always keep at least N most-recent logs (default 10)
  keep_escalated:  bool — never evict tickets in tickets/failed/ (default true)
"""

from pathlib import Path


def prune_logs(
    log_dir: str,
    fail_dir: str,
    max_on_disk: int = 100,
    min_retain: int = 10,
    keep_escalated: bool = True,
) -> int:
    """
    FIFO eviction of -attempts.jsonl and paired -result.txt files.

    Eviction order: oldest by mtime first.
    Never evicts: escalated tickets (in fail_dir) or the min_retain most recent.

    Args:
        log_dir:        Path to logs/ directory
        fail_dir:       Path to tickets/failed/ directory
        max_on_disk:    Maximum number of -attempts.jsonl files to keep
        min_retain:     Always retain at least this many most-recent logs
        keep_escalated: If True, never evict tickets present in fail_dir

    Returns:
        Number of log pairs pruned
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return 0

    # All attempt logs, sorted oldest mtime first
    attempt_logs = sorted(
        log_path.glob("*-attempts.jsonl"),
        key=lambda p: p.stat().st_mtime
    )

    total = len(attempt_logs)
    if total <= max_on_disk:
        return 0

    protected = _get_protected_ids(fail_dir) if keep_escalated else set()

    # Always retain the min_retain most-recent stems
    retain_tail = {p.stem for p in attempt_logs[-min_retain:]} if min_retain > 0 else set()

    evictable = [
        p for p in attempt_logs
        if _ticket_id(p) not in protected
        and p.stem not in retain_tail
    ]

    to_prune = total - max_on_disk
    pruned = 0

    for log_file in evictable[:to_prune]:
        tid = _ticket_id(log_file)
        log_file.unlink(missing_ok=True)
        result_file = log_path / f"{tid}-result.txt"
        result_file.unlink(missing_ok=True)
        pruned += 1

    return pruned


def _ticket_id(attempt_log_path: Path) -> str:
    """Extract ticket ID from a -attempts.jsonl path.
    e.g. logs/TASK-042-attempts.jsonl -> TASK-042
    """
    return attempt_log_path.stem.replace("-attempts", "")


def _get_protected_ids(fail_dir: str) -> set:
    """Return set of ticket IDs present in tickets/failed/.
    These are escalated tickets — never evict their logs.
    """
    fail_path = Path(fail_dir)
    if not fail_path.exists():
        return set()
    return {p.stem for p in fail_path.glob("*.yaml")}
