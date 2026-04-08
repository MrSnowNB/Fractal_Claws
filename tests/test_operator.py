"""
Operator Unit Tests

Covers: Operator init, Ticket creation/from_dict/to_dict, status alias coercion,
title field, round-trip fidelity, task decomposition, validation gates,
failure handling, and stats.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operator_v7 import (
    Operator,
    Ticket,
    TicketStatus,
    TicketPriority,
    _STATUS_ALIAS,
    _PRIORITY_ALIAS,
)


# ---------------------------------------------------------------------------
# Operator init
# ---------------------------------------------------------------------------

class TestOperatorInit:
    """Test suite: Operator initialization."""

    def test_operator_init(self):
        """Operator initializes correctly."""
        op = Operator()
        assert op.base_dir.exists()
        assert len(op.tickets) == 0
        assert op.logger is not None


# ---------------------------------------------------------------------------
# Ticket creation
# ---------------------------------------------------------------------------

class TestTicketCreation:
    """Test suite: Ticket creation and management."""

    def test_ticket_creation(self):
        """Ticket can be created with correct defaults."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-001", depth=0, priority="high")
        assert isinstance(ticket, Ticket)
        assert ticket.id == "TASK-001"
        assert ticket.depth == 0
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.status == TicketStatus.PENDING
        assert ticket.title == ""

    def test_ticket_creation_with_title(self):
        """Ticket can be created with an explicit title."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-T01", title="My Task")
        assert ticket.title == "My Task"

    def test_ticket_from_dict_id_key(self):
        """from_dict() accepts 'id' key (runner/YAML format)."""
        data = {
            "id": "TASK-002",
            "depth": 1,
            "parent": "TASK-001",
            "children": [],
            "status": "pending",
            "attempts": 0,
            "decrement": 3,
            "priority": "medium",
            "result": {},
        }
        ticket = Ticket.from_dict(data)
        assert ticket.id == "TASK-002"
        assert ticket.depth == 1
        assert ticket.parent == "TASK-001"
        assert ticket.status == TicketStatus.PENDING

    def test_ticket_from_dict_ticket_id_key(self):
        """from_dict() accepts 'ticket_id' key (to_dict() canonical format)."""
        data = {"ticket_id": "TASK-002B", "status": "pending", "priority": "low"}
        ticket = Ticket.from_dict(data)
        assert ticket.id == "TASK-002B"

    def test_ticket_from_dict_no_id_raises(self):
        """from_dict() raises ValueError when neither id nor ticket_id present."""
        with pytest.raises(ValueError, match="ticket_id or id required"):
            Ticket.from_dict({"depth": 1})

    def test_ticket_to_dict(self):
        """to_dict() returns canonical keys with correct values."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-003", depth=2, priority="low")
        data = ticket.to_dict()
        assert data["ticket_id"] == "TASK-003"
        assert data["depth"] == 2
        assert data["priority"] == "low"
        assert data["title"] == ""
        assert data["status"] == "pending"

    def test_ticket_to_dict_includes_title(self):
        """to_dict() includes title field."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-T02", title="Fix the bug")
        data = ticket.to_dict()
        assert data["title"] == "Fix the bug"

    def test_ticket_round_trip(self):
        """Ticket survives to_dict() → from_dict() round-trip with no data loss."""
        op = Operator()
        original = op.create_ticket(
            id="TASK-RT",
            depth=1,
            priority="high",
            title="Round trip test",
            rationale="ensure fidelity",
            tags=["ci", "gate"],
        )
        data = original.to_dict()
        restored = Ticket.from_dict(data)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.depth == original.depth
        assert restored.priority == original.priority
        assert restored.status == original.status
        assert restored.rationale == original.rationale
        assert restored.tags == original.tags


# ---------------------------------------------------------------------------
# Status alias coercion  (the core fix for the 2 pre-existing failures)
# ---------------------------------------------------------------------------

class TestStatusAliasCoercion:
    """Test suite: Runner YAML status alias coercion in from_dict()."""

    def test_status_open_coerced_to_pending(self):
        """'open' (runner YAML) is coerced to TicketStatus.PENDING."""
        ticket = Ticket.from_dict({"id": "SA-001", "status": "open"})
        assert ticket.status == TicketStatus.PENDING

    def test_status_failed_coerced_to_escalated(self):
        """'failed' (runner YAML) is coerced to TicketStatus.ESCALATED."""
        ticket = Ticket.from_dict({"id": "SA-002", "status": "failed"})
        assert ticket.status == TicketStatus.ESCALATED

    def test_status_in_progress_coerced_to_pending(self):
        """'in_progress' is coerced to TicketStatus.PENDING."""
        ticket = Ticket.from_dict({"id": "SA-003", "status": "in_progress"})
        assert ticket.status == TicketStatus.PENDING

    def test_status_running_coerced_to_pending(self):
        """'running' is coerced to TicketStatus.PENDING."""
        ticket = Ticket.from_dict({"id": "SA-004", "status": "running"})
        assert ticket.status == TicketStatus.PENDING

    def test_status_pending_passthrough(self):
        """'pending' (canonical) passes through unchanged."""
        ticket = Ticket.from_dict({"id": "SA-005", "status": "pending"})
        assert ticket.status == TicketStatus.PENDING

    def test_status_escalated_passthrough(self):
        """'escalated' (canonical) passes through unchanged."""
        ticket = Ticket.from_dict({"id": "SA-006", "status": "escalated"})
        assert ticket.status == TicketStatus.ESCALATED

    def test_status_closed_passthrough(self):
        """'closed' (canonical) passes through unchanged."""
        ticket = Ticket.from_dict({"id": "SA-007", "status": "closed"})
        assert ticket.status == TicketStatus.CLOSED

    def test_unknown_status_raises(self):
        """An unrecognised status string raises ValueError."""
        with pytest.raises(ValueError):
            Ticket.from_dict({"id": "SA-008", "status": "banana"})

    def test_alias_map_exported(self):
        """_STATUS_ALIAS is exported and contains expected keys."""
        assert "open" in _STATUS_ALIAS
        assert "failed" in _STATUS_ALIAS
        assert _STATUS_ALIAS["open"] == "pending"
        assert _STATUS_ALIAS["failed"] == "escalated"


# ---------------------------------------------------------------------------
# Priority alias coercion
# ---------------------------------------------------------------------------

class TestPriorityAliasCoercion:
    """Test suite: Priority alias coercion in from_dict()."""

    def test_priority_urgent_coerced_to_critical(self):
        """'urgent' is coerced to TicketPriority.CRITICAL."""
        ticket = Ticket.from_dict({"id": "PA-001", "priority": "urgent"})
        assert ticket.priority == TicketPriority.CRITICAL

    def test_priority_high_passthrough(self):
        """'high' passes through unchanged."""
        ticket = Ticket.from_dict({"id": "PA-002", "priority": "high"})
        assert ticket.priority == TicketPriority.HIGH

    def test_unknown_priority_raises(self):
        """An unrecognised priority string raises ValueError."""
        with pytest.raises(ValueError):
            Ticket.from_dict({"id": "PA-003", "priority": "potato"})


# ---------------------------------------------------------------------------
# Title field
# ---------------------------------------------------------------------------

class TestTitleField:
    """Test suite: Ticket title field."""

    def test_title_defaults_to_empty_string(self):
        """Ticket.title defaults to empty string."""
        ticket = Ticket(id="TF-001")
        assert ticket.title == ""

    def test_title_round_trip(self):
        """Title survives to_dict() → from_dict()."""
        ticket = Ticket(id="TF-002", title="Hello World")
        restored = Ticket.from_dict(ticket.to_dict())
        assert restored.title == "Hello World"

    def test_title_in_to_dict(self):
        """to_dict() includes 'title' key."""
        ticket = Ticket(id="TF-003", title="Deploy gateway")
        d = ticket.to_dict()
        assert "title" in d
        assert d["title"] == "Deploy gateway"

    def test_title_from_yaml_dict(self):
        """from_dict() reads 'title' from YAML-style dict."""
        ticket = Ticket.from_dict({"id": "TF-004", "title": "From YAML"})
        assert ticket.title == "From YAML"

    def test_title_missing_from_dict_defaults_empty(self):
        """from_dict() silently defaults title to '' when key absent."""
        ticket = Ticket.from_dict({"id": "TF-005"})
        assert ticket.title == ""


# ---------------------------------------------------------------------------
# Task decomposition
# ---------------------------------------------------------------------------

class TestTaskDecomposition:
    """Test suite: Task decomposition."""

    def test_first_principles_breakdown(self):
        """First principles breakdown returns 5 components."""
        op = Operator()
        subtasks = op._first_principles_breakdown("Build a web application")
        assert isinstance(subtasks, list)
        assert len(subtasks) == 5
        assert subtasks[0]["name"] == "analyze_requirements"

    def test_first_principles_all_names_present(self):
        """All 5 expected step names are present."""
        op = Operator()
        subtasks = op._first_principles_breakdown("X")
        names = [s["name"] for s in subtasks]
        assert "analyze_requirements" in names
        assert "design_solution" in names
        assert "identify_components" in names
        assert "define_interfaces" in names
        assert "validate_approach" in names

    def test_recursive_decomposition(self):
        """Recursive decomposition returns 3 steps."""
        op = Operator()
        subtasks = op._recursive_decomposition("Implement feature X")
        assert isinstance(subtasks, list)
        assert len(subtasks) == 3

    def test_recursive_decomposition_step_names(self):
        """Recursive decomposition step names are correct."""
        op = Operator()
        subtasks = op._recursive_decomposition("X")
        names = [s["name"] for s in subtasks]
        assert "define_subtask" in names
        assert "execute_subtask" in names
        assert "validate_subtask" in names


# ---------------------------------------------------------------------------
# Validation gates
# ---------------------------------------------------------------------------

class TestValidationGates:
    """Test suite: Validation gates."""

    def test_validate_method(self):
        """Validate method returns gate results with all_passed True."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-004")
        result = op.validate(ticket)
        assert "all_passed" in result
        assert "gate_results" in result
        assert result["all_passed"] is True

    def test_validate_gate_keys(self):
        """Gate results contain expected gate names."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-004B")
        result = op.validate(ticket)
        gates = result["gate_results"]
        assert "unit_test" in gates
        assert "lint" in gates
        assert "type_check" in gates


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestFailureHandling:
    """Test suite: Failure handling procedure."""

    def test_handle_failure_raises_exit(self):
        """Failure handling raises SystemExit containing ticket id."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-005")
        with pytest.raises(SystemExit) as exc_info:
            op.handle_failure(ticket, Exception("Test failure"))
        assert "TASK-005" in str(exc_info.value)

    def test_capture_logs_creates_file(self):
        """capture_logs() writes an ISS-*.log file."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-006")
        op.capture_logs(ticket, Exception("Test error"))
        log_dir = op.base_dir / "logs"
        assert log_dir.exists()
        assert len(list(log_dir.glob("ISS-*.log"))) >= 1


# ---------------------------------------------------------------------------
# Operator stats
# ---------------------------------------------------------------------------

class TestOperatorStats:
    """Test suite: Operator statistics."""

    def test_get_stats(self):
        """Stats return correct total and pending counts."""
        op = Operator()
        op.create_ticket(id="TASK-007", priority="high")
        op.create_ticket(id="TASK-008", priority="low")
        op.create_ticket(id="TASK-009", priority="critical")
        stats = op.get_stats()
        assert stats["total_tickets"] == 3
        assert stats["pending_tickets"] == 3

    def test_get_stats_closed(self):
        """closed_tickets count is total minus pending."""
        op = Operator()
        t1 = op.create_ticket(id="TASK-S1")
        t2 = op.create_ticket(id="TASK-S2")
        t2.status = TicketStatus.CLOSED
        stats = op.get_stats()
        assert stats["total_tickets"] == 2
        assert stats["pending_tickets"] == 1
        assert stats["closed_tickets"] == 1
