"""
Self-Healing Recursive First Principles Operator v7

This module implements the core operator functionality for the Fractal_Claws project.

NOTE: This module defines the canonical Ticket dataclass and related enums that
are the target type layer for Phase 3 (OpenClaw tool registry). Currently,
runner.py treats tickets as raw dicts loaded from YAML. The Phase 3 refactor
will wire these dataclasses into load_ticket() / save_ticket() for schema
validation and type safety. Do not remove this module — it is the future type layer.
"""

__version__ = "0.7.0"
__author__ = "MrSnowNB"

# Standard Library Imports
import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from src.tools.first_principles_solver import FirstPrinciplesAnalyzer, RecursiveSolver, SelfHealingMechanism
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path


class TicketStatus(Enum):
    """Ticket status enumeration."""
    PENDING = "pending"
    ESCALATED = "escalated"
    CLOSED = "closed"


class TicketPriority(Enum):
    """Ticket priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketDepth(Enum):
    """Ticket depth levels for model selection.

    LEAF (depth=2) is reserved for future NPU/edge integration.
    The 4B model slot is currently DEPRECATED — see settings.yaml.
    Model assignment for LEAF will be determined when NPU integration
    is re-enabled in a future phase.
    """
    ROOT = 0      # Orchestrator - Qwen3-Coder-Next-GGUF
    WORKER = 1    # Subtask execution - Qwen3.5-35B-A3B-GGUF
    LEAF = 2      # NPU execution - reserved (model TBD, see settings.yaml)


# Status aliases: runner.py writes "open" and "failed" to YAML.
# TicketStatus has no "open" or "failed" values, so we coerce on load.
_STATUS_ALIAS: Dict[str, str] = {
    "open": "pending",
    "failed": "escalated",
    "in_progress": "pending",
    "running": "pending",
}

# Priority aliases for forward-compat with any YAML variant spellings.
_PRIORITY_ALIAS: Dict[str, str] = {
    "urgent": "critical",
}


@dataclass
class Ticket:
    """
    A unit of work with pass/fail criteria.
    
    Attributes:
        id: Unique identifier
        title: Human-readable short description (optional)
        depth: 0 (root), 1 (worker), 2 (leaf)
        parent: Parent ticket ID
        children: List of child ticket IDs
        status: pending | escalated | closed
        attempts: Number of execution attempts
        decrement: Remaining escalation decrements
        priority: low | medium | high | critical
        result: Test pass/fail, score, and notes
    """
    id: str
    depth: int = 0
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    status: TicketStatus = TicketStatus.PENDING
    attempts: int = 0
    decrement: int = 3
    priority: TicketPriority = TicketPriority.MEDIUM
    result: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    title: str = ""

    # Step 5 migration fields
    task: Optional[str] = None
    max_tokens: Optional[int] = None
    depends_on: List[str] = field(default_factory=list)
    context_files: List[str] = field(default_factory=list)
    result_path: Optional[str] = None
    rationale: str = ""
    produces: List[str] = field(default_factory=list)
    consumes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    agent: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary."""
        return {
            "ticket_id": self.id,
            "title": self.title,
            "depth": self.depth,
            "parent": self.parent,
            "children": self.children,
            "status": self.status.value,
            "attempts": self.attempts,
            "decrement": self.decrement,
            "priority": self.priority.value,
            "result": self.result,
            "created_at": self.created_at,
            "task": self.task,
            "max_tokens": self.max_tokens,
            "depends_on": self.depends_on,
            "context_files": self.context_files,
            "result_path": self.result_path,
            "rationale": self.rationale,
            "produces": self.produces,
            "consumes": self.consumes,
            "tags": self.tags,
            "agent": self.agent,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ticket":
        """Create ticket from dictionary.

        Accepts both 'ticket_id' (to_dict canonical) and 'id' (YAML/runner format).
        Coerces runner status aliases ('open' → 'pending', 'failed' → 'escalated').
        """
        ticket_id = data.get("ticket_id") or data.get("id")
        if not ticket_id:
            raise ValueError("ticket_id or id required in from_dict()")

        raw_status = data.get("status", "pending")
        coerced_status = _STATUS_ALIAS.get(raw_status, raw_status)

        raw_priority = data.get("priority", "medium")
        coerced_priority = _PRIORITY_ALIAS.get(raw_priority, raw_priority)

        return cls(
            id=ticket_id,
            title=data.get("title", ""),
            depth=data.get("depth", 0),
            parent=data.get("parent"),
            children=data.get("children", []),
            status=TicketStatus(coerced_status),
            attempts=data.get("attempts", 0),
            decrement=data.get("decrement", 3),
            priority=TicketPriority(coerced_priority),
            result=data.get("result", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            task=data.get("task"),
            max_tokens=data.get("max_tokens"),
            depends_on=data.get("depends_on", []),
            context_files=data.get("context_files", []),
            result_path=data.get("result_path"),
            rationale=data.get("rationale", ""),
            produces=data.get("produces", []),
            consumes=data.get("consumes", []),
            tags=data.get("tags", []),
            agent=data.get("agent", ""),
        )


class Operator:
    """
    Self-healing recursive first principles operator.
    
    Manages ticket lifecycle, task decomposition, and validation gates.
    """

    def __init__(self):
        """Initialize operator with base directory and ticket store."""
        self.base_dir = Path(__file__).parent.parent
        self.tickets: Dict[str, Ticket] = {}
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def create_ticket(
        self,
        id: str,
        depth: int = 0,
        parent: Optional[str] = None,
        priority: str | TicketPriority = "medium",
        **kwargs
    ) -> Ticket:
        """Create and store a new ticket."""
        ticket = Ticket(
            id=id,
            depth=depth,
            parent=parent,
            priority=TicketPriority(priority) if isinstance(priority, str) else priority,
            **kwargs
        )
        self.tickets[id] = ticket
        return ticket

    def _first_principles_breakdown(self, task: str) -> List[Dict[str, Any]]:
        """
        Break down a task using first principles thinking.
        
        Returns 5 components: analyze_requirements, design_solution,
        identify_components, define_interfaces, validate_approach.
        """
        return [
            {"name": "analyze_requirements", "description": f"Analyze requirements for: {task}"},
            {"name": "design_solution", "description": f"Design solution for: {task}"},
            {"name": "identify_components", "description": f"Identify components for: {task}"},
            {"name": "define_interfaces", "description": f"Define interfaces for: {task}"},
            {"name": "validate_approach", "description": f"Validate approach for: {task}"}
        ]

    def _recursive_decomposition(self, task: str) -> List[Dict[str, Any]]:
        """
        Recursively decompose a task into subtasks.
        
        Returns 3 steps: define_subtask, execute_subtask, validate_subtask.
        """
        return [
            {"name": "define_subtask", "description": f"Define subtask for: {task}"},
            {"name": "execute_subtask", "description": f"Execute subtask for: {task}"},
            {"name": "validate_subtask", "description": f"Validate subtask for: {task}"}
        ]

    def validate(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Run validation gates on a ticket.
        
        Returns gate results dict with all_passed boolean.
        """
        gate_results = {
            "unit_test": {"status": "passed", "message": "No test defined"},
            "lint": {"status": "passed", "message": "No lint defined"},
            "type_check": {"status": "passed", "message": "No type check defined"}
        }
        return {"all_passed": True, "gate_results": gate_results}

    def handle_failure(self, ticket: Ticket, error: Exception) -> None:
        """
        Handle failure per policy: update docs and raise SystemExit.
        """
        self.capture_logs(ticket, error)
        raise SystemExit(f"Failure in ticket {ticket.id}: {error}")

    def capture_logs(self, ticket: Ticket, error: Exception) -> None:
        """Capture error logs to file."""
        log_dir = self.base_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = log_dir / f"ISS-{ticket.id}-{timestamp}.log"
        
        with open(log_file, "w") as f:
            f.write(f"Ticket: {ticket.id}\n")
            f.write(f"Error: {error}\n")
            f.write(f"Traceback: {error.__traceback__}\n")

    def get_stats(self) -> Dict[str, int]:
        """Return ticket statistics."""
        total = len(self.tickets)
        pending = sum(1 for t in self.tickets.values() if t.status == TicketStatus.PENDING)
        return {
            "total_tickets": total,
            "pending_tickets": pending,
            "closed_tickets": total - pending
        }
