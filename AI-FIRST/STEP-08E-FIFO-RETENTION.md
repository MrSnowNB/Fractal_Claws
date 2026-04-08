# STEP-08E — FIFO Log Retention Policy

> **AI-FIRST DOC** — Full spec for Luffy to implement and validate.
> No model calls. No endpoints. Pure file I/O.

---

## Why This Step Exists

Every ticket execution writes two files to `logs/`:
- `<ticket_id>-attempts.jsonl` — the full attempt audit trail
- `<ticket_id>-result.txt` — the raw model + tool output

Over a long run (hundreds of tickets), `logs/` grows unbounded. On the ZBook,
disk is constrained. More critically, on Liberty Mesh nodes, storage is
extremely limited (LoRa-connected edge devices). The FIFO policy evicts the
oldest log pairs first, while protecting escalated (failed) tickets that need
human review.

This step is **pure file I/O** — no model, no endpoint, no API key required.
Luffy can build and validate it entirely offline.

---

## What to Build

### 1. `agent/log_manager.py` — new file

```python
"""
log_manager.py — FIFO retention policy for logs/

Evicts oldest -attempts.jsonl / -result.txt pairs when log count exceeds
max_on_disk. Never evicts escalated tickets (those in tickets/failed/).

Called from:
  - runner.drain()       — at drain entry, before any tickets execute
  - execute_ticket()     — after every PASS close

Settings keys (all in settings.yaml under logging:):
  max_logs:         int  — max -attempts.jsonl files on disk (default 100)
  min_retain:       int  — always keep at least N most-recent logs (default 10)
  keep_escalated:   bool — never evict tickets in tickets/failed/ (default true)
"""

import os
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

    # All attempt logs, oldest mtime first
    attempt_logs = sorted(
        log_path.glob("*-attempts.jsonl"),
        key=lambda p: p.stat().st_mtime
    )

    total = len(attempt_logs)
    if total <= max_on_disk:
        return 0

    protected = _get_protected_ids(fail_dir) if keep_escalated else set()

    # Candidates = oldest first, excluding protected and the min_retain most recent
    retain_tail = set(p.stem for p in attempt_logs[-min_retain:])

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
    These are escalated tickets and must never be evicted.
    """
    fail_path = Path(fail_dir)
    if not fail_path.exists():
        return set()
    return {p.stem for p in fail_path.glob("*.yaml")}
```

---

### 2. `settings.yaml` — add three keys under `logging:`

```yaml
logging:
  dir: logs/
  pattern: "logs/session_{date}.jsonl"
  gitignore: true
  max_logs: 100          # FIFO eviction ceiling
  min_retain: 10         # always keep N most-recent regardless of count
  keep_escalated: true   # escalated tickets (in tickets/failed/) are never evicted
```

---

### 3. `agent/runner.py` — two call sites

**Import at top of runner.py:**
```python
from agent.log_manager import prune_logs
```

**Call site 1 — in `drain()`, before the while loop:**
```python
prune_logs(
    log_dir=LOG_DIR,
    fail_dir=FAIL_DIR,
    max_on_disk=int(CFG["logging"].get("max_logs", 100)),
    min_retain=int(CFG["logging"].get("min_retain", 10)),
    keep_escalated=bool(CFG["logging"].get("keep_escalated", True)),
)
```

**Call site 2 — in `execute_ticket()`, inside the `if passed:` block after `save_ticket(dest, ticket)`:**
```python
prune_logs(
    log_dir=LOG_DIR,
    fail_dir=FAIL_DIR,
    max_on_disk=int(CFG["logging"].get("max_logs", 100)),
    min_retain=int(CFG["logging"].get("min_retain", 10)),
    keep_escalated=bool(CFG["logging"].get("keep_escalated", True)),
)
```

---

## Validation Gate

```
pytest tests/test_log_manager.py -v
pytest tests/ -v
```

Expected: all tests pass, 1 skipped (platform), 0 failed.

---

## Invariants

- `prune_logs()` never deletes files in `tickets/` — only in `logs/`
- Escalated ticket logs survive regardless of count
- `min_retain` most-recent logs always survive regardless of count
- `prune_logs()` is idempotent — calling it twice changes nothing if count is within bounds
- No model, no endpoint, no API key required — pure file I/O

---

## Context Files (for Luffy)

```yaml
context_files:
  - AI-FIRST/STEP-08E-FIFO-RETENTION.md
  - agent/log_manager.py
  - settings.yaml
  - agent/runner.py
  - tests/test_log_manager.py
```
