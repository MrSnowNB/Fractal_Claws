"""
Operator Unit Tests

This module contains unit tests for the Operator class.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operator_v7 import Operator, Ticket, TicketStatus, TicketPriority


class TestOperatorInit:
    """Test suite: Operator initialization."""

    def test_operator_init(self):
        """Operator initializes correctly."""
        op = Operator()
        assert op.base_dir.exists()
        assert len(op.tickets) == 0
        assert op.logger is not None


class TestTicketCreation:
    """Test suite: Ticket creation and management."""

    def test_ticket_creation(self):
        """Ticket can be created."""
        op = Operator()
        ticket = op.create_ticket(
            id="TASK-001",
            depth=0,
            priority="high"
        )
        assert isinstance(ticket, Ticket)
        assert ticket.id == "TASK-001"
        assert ticket.depth == 0
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.status == TicketStatus.PENDING

    def test_ticket_from_dict(self):
        """Ticket can be created from dictionary."""
        data = {
            "id": "TASK-002",
            "depth": 1,
            "parent": "TASK-001",
            "children": [],
            "status": "pending",
            "attempts": 0,
            "decrement": 3,
            "priority": "medium",
            "result": {}
        }
        ticket = Ticket.from_dict(data)
        assert ticket.id == "TASK-002"
        assert ticket.depth == 1
        assert ticket.parent == "TASK-001"

    def test_ticket_to_dict(self):
        """Ticket can be converted to dictionary."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-003", depth=2, priority="low")
        data = ticket.to_dict()
        assert data["ticket_id"] == "TASK-003"
        assert data["depth"] == 2
        assert data["priority"] == "low"


class TestTaskDecomposition:
    """Test suite: Task decomposition."""

    def test_first_principles_breakdown(self):
        """First principles breakdown returns components."""
        op = Operator()
        task = "Build a web application"
        subtasks = op._first_principles_breakdown(task)
        assert isinstance(subtasks, list)
        assert len(subtasks) == 5
        assert subtasks[0]["name"] == "analyze_requirements"

    def test_recursive_decomposition(self):
        """Recursive decomposition returns steps."""
        op = Operator()
        task = "Implement feature X"
        subtasks = op._recursive_decomposition(task)
        assert isinstance(subtasks, list)
        assert len(subtasks) == 3


class TestValidationGates:
    """Test suite: Validation gates."""

    def test_validate_method(self):
        """Validate method returns gate results."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-004")
        result = op.validate(ticket)
        assert "all_passed" in result
        assert "gate_results" in result
        assert result["all_passed"] is True


class TestFailureHandling:
    """Test suite: Failure handling procedure."""

    def test_handle_failure_raises_exit(self):
        """Failure handling raises SystemExit after updating docs."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-005")
        error = Exception("Test failure")
        
        with pytest.raises(SystemExit) as exc_info:
            op.handle_failure(ticket, error)
        
        assert "TASK-005" in str(exc_info.value)

    def test_capture_logs_creates_file(self):
        """Logs are captured to file."""
        op = Operator()
        ticket = op.create_ticket(id="TASK-006")
        error = Exception("Test error")
        
        op.capture_logs(ticket, error)
        
        log_dir = op.base_dir / "logs"
        assert log_dir.exists()
        log_files = list(log_dir.glob("ISS-*.log"))
        assert len(log_files) >= 1


class TestOperatorStats:
    """Test suite: Operator statistics."""

    def test_get_stats(self):
        """Stats return correct counts."""
        op = Operator()
        op.create_ticket(id="TASK-007", priority="high")
        op.create_ticket(id="TASK-008", priority="low")
        op.create_ticket(id="TASK-009", priority="critical")
        
        stats = op.get_stats()
        assert stats["total_tickets"] == 3
        assert stats["pending_tickets"] == 3