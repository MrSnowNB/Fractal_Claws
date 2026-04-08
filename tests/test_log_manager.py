"""tests/test_log_manager.py — FIFO retention policy tests for STEP-08E.

All tests use tmp_path only. No network, no model, no endpoint required.
Runnable: pytest tests/test_log_manager.py -v
"""

import time
from pathlib import Path
import pytest

from agent.log_manager import prune_logs, _ticket_id, _get_protected_ids


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_log_pair(log_dir: Path, ticket_id: str, mtime_offset: float = 0.0) -> None:
    """Write a -attempts.jsonl and -result.txt pair, then set mtime."""
    attempts = log_dir / f"{ticket_id}-attempts.jsonl"
    result   = log_dir / f"{ticket_id}-result.txt"
    attempts.write_text('{"ts": "2026-01-01", "ticket_id": "' + ticket_id + '"}\n')
    result.write_text(f"ticket: {ticket_id}\nfinish: stop\n")
    if mtime_offset != 0.0:
        t = time.time() + mtime_offset
        import os
        os.utime(attempts, (t, t))
        os.utime(result, (t, t))


def _make_failed_ticket(fail_dir: Path, ticket_id: str) -> None:
    """Write a stub escalated ticket YAML in tickets/failed/."""
    fail_dir.mkdir(parents=True, exist_ok=True)
    (fail_dir / f"{ticket_id}.yaml").write_text(
        f"id: {ticket_id}\nstatus: escalated\n"
    )


# ── _ticket_id ────────────────────────────────────────────────────────────────

def test_ticket_id_extraction(tmp_path):
    p = tmp_path / "TASK-042-attempts.jsonl"
    p.touch()
    assert _ticket_id(p) == "TASK-042"


def test_ticket_id_extraction_leading_zeros(tmp_path):
    p = tmp_path / "TASK-007-attempts.jsonl"
    p.touch()
    assert _ticket_id(p) == "TASK-007"


# ── _get_protected_ids ────────────────────────────────────────────────────────

def test_protected_ids_empty_dir(tmp_path):
    missing = str(tmp_path / "nonexistent")
    assert _get_protected_ids(missing) == set()


def test_protected_ids_populated(tmp_path):
    fail_dir = tmp_path / "tickets" / "failed"
    _make_failed_ticket(fail_dir, "TASK-001")
    _make_failed_ticket(fail_dir, "TASK-002")
    ids = _get_protected_ids(str(fail_dir))
    assert ids == {"TASK-001", "TASK-002"}


# ── prune_logs — no-op cases ──────────────────────────────────────────────────

def test_prune_noop_below_ceiling(tmp_path):
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)
    for i in range(5):
        _make_log_pair(log_dir, f"TASK-{i:03d}")
    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=2)
    assert pruned == 0
    assert len(list(log_dir.glob("*-attempts.jsonl"))) == 5


def test_prune_noop_at_ceiling(tmp_path):
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)
    for i in range(10):
        _make_log_pair(log_dir, f"TASK-{i:03d}")
    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=2)
    assert pruned == 0


def test_prune_noop_missing_log_dir(tmp_path):
    missing  = str(tmp_path / "logs_missing")
    fail_dir = str(tmp_path / "tickets" / "failed")
    pruned = prune_logs(missing, fail_dir, max_on_disk=5)
    assert pruned == 0


# ── prune_logs — basic eviction ───────────────────────────────────────────────

def test_prune_evicts_oldest_first(tmp_path):
    """12 logs, ceiling=10, min_retain=0 → 2 oldest evicted."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    # Create with staggered mtimes so ordering is deterministic
    for i in range(12):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=0)
    assert pruned == 2

    remaining = {p.stem for p in log_dir.glob("*-attempts.jsonl")}
    # Oldest two (TASK-000, TASK-001) must be gone
    assert "TASK-000-attempts" not in remaining
    assert "TASK-001-attempts" not in remaining
    # All others must remain
    for i in range(2, 12):
        assert f"TASK-{i:03d}-attempts" in remaining


def test_prune_removes_result_txt_pair(tmp_path):
    """Eviction removes both -attempts.jsonl AND -result.txt."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    for i in range(6):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    prune_logs(str(log_dir), str(fail_dir), max_on_disk=5, min_retain=0)

    assert not (log_dir / "TASK-000-attempts.jsonl").exists()
    assert not (log_dir / "TASK-000-result.txt").exists()
    # Pair for TASK-001 must still exist
    assert (log_dir / "TASK-001-attempts.jsonl").exists()


def test_prune_count_return_value(tmp_path):
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    for i in range(15):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=0)
    assert pruned == 5
    assert len(list(log_dir.glob("*-attempts.jsonl"))) == 10


# ── prune_logs — protected (escalated) tickets ────────────────────────────────

def test_prune_skips_escalated_tickets(tmp_path):
    """Escalated ticket logs are never evicted, even when oldest."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    # TASK-000 is oldest AND escalated
    _make_log_pair(log_dir, "TASK-000", mtime_offset=0.0)
    _make_failed_ticket(fail_dir, "TASK-000")

    for i in range(1, 12):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    # 12 total, ceiling=10, min_retain=0, TASK-000 is protected
    prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=0)

    # TASK-000 must survive
    assert (log_dir / "TASK-000-attempts.jsonl").exists()
    # Next oldest (TASK-001, TASK-002) are evicted instead
    assert not (log_dir / "TASK-001-attempts.jsonl").exists()
    assert not (log_dir / "TASK-002-attempts.jsonl").exists()


def test_prune_keep_escalated_false_evicts_escalated(tmp_path):
    """When keep_escalated=False, escalated tickets ARE evictable."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    _make_log_pair(log_dir, "TASK-000", mtime_offset=0.0)
    _make_failed_ticket(fail_dir, "TASK-000")
    for i in range(1, 6):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    prune_logs(str(log_dir), str(fail_dir), max_on_disk=5, min_retain=0, keep_escalated=False)

    assert not (log_dir / "TASK-000-attempts.jsonl").exists()


# ── prune_logs — min_retain ───────────────────────────────────────────────────

def test_prune_min_retain_protects_recent(tmp_path):
    """min_retain=5 keeps 5 most-recent even when eviction would take them."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    for i in range(15):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    # ceiling=5, min_retain=5 → the 5 most-recent are protected
    # only 5 evictable out of 10 candidates needed → prunes from oldest
    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=5, min_retain=5)
    assert pruned == 10

    remaining = {p.stem for p in log_dir.glob("*-attempts.jsonl")}
    # The 5 most recent (TASK-010 through TASK-014) must survive
    for i in range(10, 15):
        assert f"TASK-{i:03d}-attempts" in remaining


def test_prune_min_retain_zero_evicts_all_eligible(tmp_path):
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    for i in range(8):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=5, min_retain=0)
    assert pruned == 3
    assert len(list(log_dir.glob("*-attempts.jsonl"))) == 5


# ── prune_logs — idempotency ──────────────────────────────────────────────────

def test_prune_idempotent(tmp_path):
    """Calling prune_logs twice with same args changes nothing on second call."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    for i in range(12):
        _make_log_pair(log_dir, f"TASK-{i:03d}", mtime_offset=float(i))

    first  = prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=0)
    second = prune_logs(str(log_dir), str(fail_dir), max_on_disk=10, min_retain=0)

    assert first == 2
    assert second == 0


# ── prune_logs — no result.txt present (graceful) ────────────────────────────

def test_prune_missing_result_txt_is_graceful(tmp_path):
    """If -result.txt doesn't exist for an evicted ticket, no error is raised."""
    log_dir  = tmp_path / "logs"
    fail_dir = tmp_path / "tickets" / "failed"
    log_dir.mkdir(parents=True)

    for i in range(6):
        attempts = log_dir / f"TASK-{i:03d}-attempts.jsonl"
        attempts.write_text('{"ts": "2026-01-01"}\n')
        import os
        t = time.time() + float(i)
        os.utime(attempts, (t, t))
        # Intentionally do NOT write -result.txt

    pruned = prune_logs(str(log_dir), str(fail_dir), max_on_disk=5, min_retain=0)
    assert pruned == 1
    assert not (log_dir / "TASK-000-attempts.jsonl").exists()
