"""
test_ticket_io.py — Validation gate for Step 1: src/ticket_io.py

STEP GATE: ALL tests in this file must pass before Step 2 begins.
Run: python -m pytest tests/test_ticket_io.py -v

Design principles:
- Zero network access (no model, no endpoint)
- Zero external dependencies beyond pyyaml + pytest
- Fully deterministic — no random, no time-sensitive assertions
- Every test maps to a documented behaviour in AI-FIRST/STEP-01-TICKET-IO.md
- Tests use tmp_path fixtures: no files left behind on disk

Test sections:
  T01  load_ticket — happy path (minimal + full ticket)
  T02  load_ticket — two-document YAML merge (legacy format)
  T03  load_ticket — field defaults applied
  T04  load_ticket — status alias coercion
  T05  load_ticket — priority coercion + unknown value fallback
  T06  load_ticket — error cases (missing file, bad YAML, missing ticket_id)
  T07  save_ticket — Ticket dataclass round-trip
  T08  save_ticket — dict passthrough (backward compat)
  T09  save_ticket — status alias: pending -> open on write
  T10  as_dict — returns flat dict from Ticket or dict input
  T11  move_ticket — moves file, returns new path
  T12  move_ticket — raises TicketIOError if source missing
  T13  scan_dir — loads all YAMLs, skips corrupt files
  T14  ticket_exists — true/false checks
  T15  round-trip fidelity — _extras survive load -> save -> load
  T16  runner.py compat — as_dict() result usable with .get() syntax
"""

import os
import textwrap
import pytest
import yaml

from src.ticket_io import (
    load_ticket,
    save_ticket,
    as_dict,
    move_ticket,
    scan_dir,
    ticket_exists,
    TicketIOError,
)
from src.operator_v7 import Ticket, TicketStatus, TicketPriority


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_YAML = textwrap.dedent("""\
    ticket_id: TASK-001
    task: Write output/hello.py and execute it.
""")

FULL_YAML = textwrap.dedent("""\
    ticket_id: TASK-002
    title: Full ticket example
    task: Write output/fib.py and verify output contains 55.
    rationale: Demonstrates full field set.
    produces:
      - output/fib.py
      - stdout:fib-10
    consumes: []
    tags:
      - fibonacci
      - numeric-output
    depends_on:
      - TASK-001
    allowed_tools:
      - write_file
      - exec_python
    agent: test-agent
    status: open
    depth: 1
    max_depth: 2
    decrement: 2
    priority: high
    result_path: logs/TASK-002-result.txt
    context_files: []
    result:
      score: 0.95
""")

TWO_DOC_YAML = textwrap.dedent("""\
    ticket_id: TASK-003
    task: Base document task.
    status: open
    ---
    depth: 1
    priority: critical
""")


def _write(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# T01 — load_ticket happy path
# ---------------------------------------------------------------------------

class TestLoadTicketHappyPath:

    def test_minimal_ticket_loads(self, tmp_path):
        """Minimal YAML with only ticket_id + task loads without error."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = load_ticket(path)
        assert isinstance(ticket, Ticket)
        assert ticket.id == "TASK-001"

    def test_full_ticket_loads(self, tmp_path):
        """Full YAML with all fields loads and maps correctly."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = load_ticket(path)
        assert ticket.id == "TASK-002"
        assert ticket.depth == 1
        assert ticket.decrement == 2
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.result == {"score": 0.95}

    def test_extras_attached(self, tmp_path):
        """Runner extras (task, depends_on, tags, etc.) attach as _extras."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = load_ticket(path)
        extras = ticket._extras
        assert extras["task"] == "Write output/fib.py and verify output contains 55."
        assert extras["depends_on"] == ["TASK-001"]
        assert "fibonacci" in extras["tags"]
        assert extras["agent"] == "test-agent"


# ---------------------------------------------------------------------------
# T02 — Two-document YAML merge
# ---------------------------------------------------------------------------

class TestTwoDocumentYAML:

    def test_two_doc_merge(self, tmp_path):
        """Second YAML document overlays first (legacy runner format)."""
        path = _write(tmp_path, "TASK-003.yaml", TWO_DOC_YAML)
        ticket = load_ticket(path)
        assert ticket.id == "TASK-003"
        # overlay doc sets depth=1, priority=critical
        assert ticket.depth == 1
        assert ticket.priority == TicketPriority.CRITICAL


# ---------------------------------------------------------------------------
# T03 — Field defaults
# ---------------------------------------------------------------------------

class TestFieldDefaults:

    def test_defaults_applied_to_minimal(self, tmp_path):
        """Optional fields default correctly when absent from YAML."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = load_ticket(path)
        assert ticket.depth == 0
        assert ticket.decrement == 3
        assert ticket.attempts == 0
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.status == TicketStatus.PENDING
        assert ticket.children == []
        assert ticket.result == {}
        assert ticket.parent is None

    def test_extras_defaults(self, tmp_path):
        """Runner extras default to empty lists/strings when absent."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = load_ticket(path)
        extras = ticket._extras
        assert extras.get("depends_on", []) == []
        assert extras.get("tags", []) == []
        assert extras.get("produces", []) == []


# ---------------------------------------------------------------------------
# T04 — Status alias coercion
# ---------------------------------------------------------------------------

class TestStatusCoercion:

    @pytest.mark.parametrize("raw,expected", [
        ("open",      TicketStatus.PENDING),
        ("pending",   TicketStatus.PENDING),
        ("closed",    TicketStatus.CLOSED),
        ("escalated", TicketStatus.ESCALATED),
        ("failed",    TicketStatus.ESCALATED),
    ])
    def test_status_aliases(self, tmp_path, raw, expected):
        """All known status strings coerce to the correct TicketStatus enum."""
        content = f"ticket_id: TASK-S\ntask: test\nstatus: {raw}\n"
        path = _write(tmp_path, "TASK-S.yaml", content)
        ticket = load_ticket(path)
        assert ticket.status == expected

    def test_unknown_status_defaults_to_pending(self, tmp_path):
        """Unknown status string coerces to PENDING (no exception raised)."""
        content = "ticket_id: TASK-X\ntask: test\nstatus: banana\n"
        path = _write(tmp_path, "TASK-X.yaml", content)
        ticket = load_ticket(path)  # must not raise
        assert ticket.status == TicketStatus.PENDING


# ---------------------------------------------------------------------------
# T05 — Priority coercion
# ---------------------------------------------------------------------------

class TestPriorityCoercion:

    @pytest.mark.parametrize("raw,expected", [
        ("low",      TicketPriority.LOW),
        ("medium",   TicketPriority.MEDIUM),
        ("high",     TicketPriority.HIGH),
        ("critical", TicketPriority.CRITICAL),
    ])
    def test_valid_priorities(self, tmp_path, raw, expected):
        content = f"ticket_id: TASK-P\ntask: test\npriority: {raw}\n"
        path = _write(tmp_path, "TASK-P.yaml", content)
        ticket = load_ticket(path)
        assert ticket.priority == expected

    def test_unknown_priority_defaults_to_medium(self, tmp_path):
        """Unknown priority coerces to MEDIUM without raising."""
        content = "ticket_id: TASK-P\ntask: test\npriority: ultramax\n"
        path = _write(tmp_path, "TASK-P.yaml", content)
        ticket = load_ticket(path)
        assert ticket.priority == TicketPriority.MEDIUM


# ---------------------------------------------------------------------------
# T06 — Error cases
# ---------------------------------------------------------------------------

class TestLoadTicketErrors:

    def test_missing_file_raises(self, tmp_path):
        """Loading a nonexistent file raises TicketIOError."""
        with pytest.raises(TicketIOError, match="not found"):
            load_ticket(str(tmp_path / "GHOST.yaml"))

    def test_bad_yaml_raises(self, tmp_path):
        """Malformed YAML raises TicketIOError."""
        path = _write(tmp_path, "BAD.yaml", "ticket_id: [unclosed\n")
        with pytest.raises(TicketIOError, match="YAML parse error"):
            load_ticket(path)

    def test_missing_ticket_id_raises(self, tmp_path):
        """YAML without ticket_id raises TicketIOError."""
        path = _write(tmp_path, "NO-ID.yaml", "task: do something\nstatus: open\n")
        with pytest.raises(TicketIOError, match="missing required field"):
            load_ticket(path)

    def test_empty_file_raises(self, tmp_path):
        """Empty YAML file raises TicketIOError."""
        path = _write(tmp_path, "EMPTY.yaml", "")
        with pytest.raises(TicketIOError):
            load_ticket(path)


# ---------------------------------------------------------------------------
# T07 — save_ticket: Ticket dataclass round-trip
# ---------------------------------------------------------------------------

class TestSaveTicketDataclass:

    def test_save_and_reload(self, tmp_path):
        """Ticket saved as dataclass reloads with identical core fields."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = load_ticket(path)

        out_path = str(tmp_path / "TASK-002-out.yaml")
        save_ticket(out_path, ticket)

        reloaded = load_ticket(out_path)
        assert reloaded.id == ticket.id
        assert reloaded.depth == ticket.depth
        assert reloaded.decrement == ticket.decrement
        assert reloaded.priority == ticket.priority

    def test_save_adds_updated_at(self, tmp_path):
        """save_ticket stamps updated_at on Ticket objects."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = load_ticket(path)
        out_path = str(tmp_path / "out.yaml")
        save_ticket(out_path, ticket)
        with open(out_path) as f:
            data = yaml.safe_load(f)
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# T08 — save_ticket: dict passthrough
# ---------------------------------------------------------------------------

class TestSaveTicketDict:

    def test_dict_written_as_is(self, tmp_path):
        """Raw dict passed to save_ticket is written without modification."""
        data = {"ticket_id": "TASK-D", "task": "test", "status": "open"}
        out_path = str(tmp_path / "TASK-D.yaml")
        save_ticket(out_path, data)
        with open(out_path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["ticket_id"] == "TASK-D"
        assert loaded["status"] == "open"


# ---------------------------------------------------------------------------
# T09 — save_ticket: status alias pending -> open
# ---------------------------------------------------------------------------

class TestSaveStatusAlias:

    def test_pending_written_as_open(self, tmp_path):
        """Ticket with PENDING status writes 'open' to YAML (runner.py compat)."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = load_ticket(path)
        assert ticket.status == TicketStatus.PENDING

        out_path = str(tmp_path / "out.yaml")
        save_ticket(out_path, ticket)
        with open(out_path) as f:
            data = yaml.safe_load(f)
        assert data["status"] == "open"


# ---------------------------------------------------------------------------
# T10 — as_dict
# ---------------------------------------------------------------------------

class TestAsDict:

    def test_ticket_to_dict(self, tmp_path):
        """as_dict() on a Ticket returns a flat dict with core fields."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = load_ticket(path)
        d = as_dict(ticket)
        assert isinstance(d, dict)
        assert d["id"] == "TASK-001"
        # status alias applied
        assert d["status"] == "open"

    def test_dict_passthrough(self):
        """as_dict() on a plain dict returns it unchanged."""
        raw = {"ticket_id": "TASK-X", "status": "open"}
        result = as_dict(raw)
        assert result is raw

    def test_as_dict_supports_get_syntax(self, tmp_path):
        """as_dict() result supports .get() — runner.py migration compat."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = load_ticket(path)
        d = as_dict(ticket)
        # runner.py call-site patterns
        assert d.get("id") == "TASK-002"
        assert d.get("depth") == 1
        assert d.get("nonexistent", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# T11 — move_ticket
# ---------------------------------------------------------------------------

class TestMoveTicket:

    def test_moves_file(self, tmp_path):
        """move_ticket relocates the file and returns the new path."""
        src = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        dst_dir = str(tmp_path / "closed")
        new_path = move_ticket(src, dst_dir)
        assert os.path.exists(new_path)
        assert not os.path.exists(src)
        assert new_path == os.path.join(dst_dir, "TASK-001.yaml")

    def test_creates_dst_dir(self, tmp_path):
        """move_ticket creates the destination directory if absent."""
        src = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        dst_dir = str(tmp_path / "new" / "nested" / "dir")
        new_path = move_ticket(src, dst_dir)
        assert os.path.exists(new_path)


# ---------------------------------------------------------------------------
# T12 — move_ticket error
# ---------------------------------------------------------------------------

class TestMoveTicketError:

    def test_missing_source_raises(self, tmp_path):
        """move_ticket raises TicketIOError if source file is missing."""
        with pytest.raises(TicketIOError, match="source not found"):
            move_ticket(str(tmp_path / "GHOST.yaml"), str(tmp_path / "dst"))


# ---------------------------------------------------------------------------
# T13 — scan_dir
# ---------------------------------------------------------------------------

class TestScanDir:

    def test_loads_all_valid(self, tmp_path):
        """scan_dir returns Ticket objects for all valid YAML files."""
        _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        tickets = scan_dir(str(tmp_path))
        assert len(tickets) == 2
        assert all(isinstance(t, Ticket) for t in tickets)

    def test_skips_corrupt(self, tmp_path):
        """scan_dir skips corrupt files without raising."""
        _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        _write(tmp_path, "CORRUPT.yaml", "ticket_id: [bad yaml\n")
        tickets = scan_dir(str(tmp_path))
        # Only the valid ticket loads; corrupt file silently skipped
        ids = [t.id for t in tickets]
        assert "TASK-001" in ids
        assert len(tickets) == 1

    def test_empty_dir_returns_empty(self, tmp_path):
        """scan_dir on an empty directory returns an empty list."""
        assert scan_dir(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# T14 — ticket_exists
# ---------------------------------------------------------------------------

class TestTicketExists:

    def test_exists_true(self, tmp_path):
        _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        assert ticket_exists("TASK-001", str(tmp_path)) is True

    def test_exists_false(self, tmp_path):
        assert ticket_exists("TASK-999", str(tmp_path)) is False


# ---------------------------------------------------------------------------
# T15 — Round-trip fidelity: _extras survive load -> save -> load
# ---------------------------------------------------------------------------

class TestRoundTripFidelity:

    def test_extras_survive_round_trip(self, tmp_path):
        """Runner extras (depends_on, tags, task, etc.) survive load/save/load."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = load_ticket(path)

        out_path = str(tmp_path / "TASK-002-rt.yaml")
        save_ticket(out_path, ticket)

        reloaded = load_ticket(out_path)
        assert reloaded._extras["depends_on"] == ["TASK-001"]
        assert "fibonacci" in reloaded._extras["tags"]
        assert reloaded._extras["result_path"] == "logs/TASK-002-result.txt"
        assert reloaded._extras["agent"] == "test-agent"


# ---------------------------------------------------------------------------
# T16 — runner.py compatibility via as_dict()
# ---------------------------------------------------------------------------

class TestRunnerCompat:

    def test_runner_pattern_ticket_id(self, tmp_path):
        """as_dict() result supports runner.py's ticket.get('ticket_id') pattern."""
        path = _write(tmp_path, "TASK-001.yaml", MINIMAL_YAML)
        ticket = as_dict(load_ticket(path))
        # runner uses both 'ticket_id' (from extras) and 'id' (from dataclass)
        # as_dict merges both
        assert ticket.get("id") == "TASK-001"

    def test_runner_pattern_depends_on(self, tmp_path):
        """as_dict() result includes depends_on from _extras."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = as_dict(load_ticket(path))
        deps = ticket.get("depends_on") or []
        assert "TASK-001" in deps

    def test_runner_pattern_depth(self, tmp_path):
        """as_dict() result includes depth directly accessible."""
        path = _write(tmp_path, "TASK-002.yaml", FULL_YAML)
        ticket = as_dict(load_ticket(path))
        assert ticket.get("depth") == 1
