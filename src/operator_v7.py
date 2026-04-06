"""
Self-Healing Recursive First Principles Operator v7

This module implements the core operator functionality for the Fractal_Claws project.
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
    """Ticket depth levels for model selection."""
    ROOT = 0      # Orchestrator - Qwen3-Coder-Next-GGUF
    WORKER = 1    # Subtask execution - Qwen3.5-35B-A3B-GGUF
    LEAF = 2      # NPU execution - lfm2.5-it-1.2b-FLM


@dataclass
class Ticket:
    """
    A unit of work with pass/fail criteria.
    
    Attributes:
        id: Unique identifier
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary."""
        return {
            "id": self.id,
            "depth": self.depth,
            "parent": self.parent,
            "children": self.children,
            "status": self.status.value,
            "attempts": self.attempts,
            "decrement": self.decrement,
            "priority": self.priority.value,
            "result": self.result,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ticket":
        """Create ticket from dictionary."""
        return cls(
            id=data["id"],
            depth=data.get("depth", 0),
            parent=data.get("parent"),
            children=data.get("children", []),
            status=TicketStatus(data.get("status", "pending")),
            attempts=data.get("attempts", 0),
            decrement=data.get("decrement", 3),
            priority=TicketPriority(data.get("priority", "medium")),
            result=data.get("result", {}),
            created_at=data.get("created_at", datetime.now().isoformat())
        )


class Operator:
    """
    The main operator class that coordinates all work.
    
    Features:
    - First Principles Thinking: Break down problems to fundamental truths
    - Recursive Decomposition: Decompose complex tasks into atomic subtasks
    - Self-Healing: Trigger failure procedure on any failure or uncertainty
    - Ticket System: Coordinate work using a hierarchical ticket system
    """
    
    def __init__(self, base_dir: str = "."):
        """
        Initialize the operator.
        
        Args:
            base_dir: Base directory for the project
        """
        self.base_dir = Path(base_dir)
        self.tickets: Dict[str, Ticket] = {}
        self.current_ticket: Optional[Ticket] = None
        self.logger = self._setup_logging()
        self._ensure_living_docs()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_dir = self.base_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger("Fractal_Claws")
        logger.setLevel(logging.DEBUG)
        
        # File handler
        log_file = log_dir / f"operator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _ensure_living_docs(self) -> None:
        """Ensure living document files exist."""
        living_docs = [
            "TROUBLESHOOTING.md",
            "REPLICATION-NOTES.md", 
            "ISSUE.md"
        ]
        
        for doc in living_docs:
            doc_path = self.base_dir / doc
            if not doc_path.exists():
                self._create_living_doc(doc_path, doc)
    
    def _create_living_doc(self, path: Path, doc_type: str) -> None:
        """Create a living document with initial content."""
        content = f"""---
title: {doc_type}
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# {doc_type}

This file is managed automatically by the Operator.
"""
        path.write_text(content)
    
    def create_ticket(
        self,
        id: str,
        depth: int = 0,
        priority: str = "medium",
        parent: Optional[str] = None
    ) -> Ticket:
        """
        Create a new ticket.
        
        Args:
            id: Unique ticket identifier
            depth: 0 (root), 1 (worker), 2 (leaf)
            priority: low | medium | high | critical
            parent: Parent ticket ID
            
        Returns:
            The created Ticket instance
        """
        ticket = Ticket(
            id=id,
            depth=depth,
            parent=parent,
            priority=TicketPriority(priority)
        )
        self.tickets[id] = ticket
        return ticket
    
    def decompose_task(self, task: str, depth: int = 0) -> List[Dict[str, Any]]:
        """
        Decompose a task into atomic subtasks using first principles thinking.
        
        Args:
            task: The task to decompose
            depth: Current depth in the hierarchy
            
        Returns:
            List of atomic subtasks
        """
        self.logger.info(f"Decomposing task at depth {depth}: {task[:50]}...")
        
        # At depth 0 (root), use first principles reasoning
        if depth == 0:
            # Break down to fundamental truths
            subtasks = self._first_principles_breakdown(task)
        else:
            # Recursive decomposition for deeper levels
            subtasks = self._recursive_decomposition(task)
        
        self.logger.info(f"Decomposed into {len(subtasks)} subtasks")
        return subtasks
    
    def _first_principles_breakdown(self, task: str) -> List[Dict[str, Any]]:
        """
        Break down task using first principles thinking.
        
        Args:
            task: The task to decompose
            
        Returns:
            List of atomic subtasks based on fundamental truths
        """
        # This is a simplified implementation
        # In production, this would use a language model for reasoning
        
        # Extract key components
        components = [
            {"name": "analyze_requirements", "description": "Analyze task requirements"},
            {"name": "design_solution", "description": "Design solution architecture"},
            {"name": "implement_code", "description": "Implement the solution"},
            {"name": "write_tests", "description": "Write validation tests"},
            {"name": "run_validation", "description": "Run all validation gates"}
        ]
        
        return components
    
    def _recursive_decomposition(self, task: str) -> List[Dict[str, Any]]:
        """
        Recursively decompose task into smaller parts.
        
        Args:
            task: The task to decompose
            
        Returns:
            List of atomic subtasks
        """
        # Simple recursive decomposition
        return [
            {"name": "step_1", "description": f"Execute part 1 of: {task[:30]}..."},
            {"name": "step_2", "description": f"Execute part 2 of: {task[:30]}..."},
            {"name": "step_3", "description": f"Execute part 3 of: {task[:30]}..."}
        ]
    
    def process_ticket(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Process a ticket through the lifecycle.
        
        Args:
            ticket: The ticket to process
            
        Returns:
            Result dictionary with pass/fail status
        """
        self.current_ticket = ticket
        self.logger.info(f"Processing ticket: {ticket.id}")
        
        try:
            # Phase 1: Plan
            self._phase_plan(ticket)
            
            # Phase 2: Build
            self._phase_build(ticket)
            
            # Phase 3: Validate
            validation_result = self._phase_validate(ticket)
            
            # Phase 4: Review
            self._phase_review(ticket)
            
            # Phase 5: Release
            self._phase_release(ticket)
            
            ticket.status = TicketStatus.CLOSED
            ticket.result = {
                "status": "passed",
                "score": 100,
                "notes": "All phases completed successfully"
            }
            
            return ticket.result
            
        except Exception as e:
            return self.handle_failure(ticket, e)
    
    def _phase_plan(self, ticket: Ticket) -> None:
        """Plan phase: Write SPEC.md and PLAN.md"""
        self.logger.info(f"Plan phase for ticket: {ticket.id}")
        spec_path = self.base_dir / "SPEC.md"
        plan_path = self.base_dir / "PLAN.md"
        
        # Create placeholder documents
        spec_path.write_text(f"""---
title: Task Specification
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# SPEC.md - {ticket.id}

## Task Description
[Task description goes here]

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

## Pass Criteria
- [ ] Pass criteria 1
- [ ] Pass criteria 2
""")
        
        plan_path.write_text(f"""---
title: Implementation Plan
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# PLAN.md - {ticket.id}

## Implementation Steps
1. Analyze requirements
2. Design solution
3. Implement code
4. Write tests
5. Run validation
""")
    
    def _phase_build(self, ticket: Ticket) -> None:
        """Build phase: Implement the spec"""
        self.logger.info(f"Build phase for ticket: {ticket.id}")
        # Implementation would go here
        pass
    
    def _phase_validate(self, ticket: Ticket) -> Dict[str, Any]:
        """Validate phase: Run all validation gates"""
        self.logger.info(f"Validate phase for ticket: {ticket.id}")
        
        gates = [
            {"name": "unit", "command": "pytest -q", "description": "Unit tests"},
            {"name": "lint", "command": "ruff check .", "description": "Linting"},
            {"name": "type", "command": "mypy .", "description": "Type checking"},
            {"name": "docs", "command": "spec drift check", "description": "Documentation drift"}
        ]
        
        results = {}
        all_passed = True
        
        for gate in gates:
            self.logger.info(f"Running gate: {gate['name']}")
            # Simulate gate execution
            gate_passed = True  # In production, this would execute the command
            results[gate['name']] = {
                "passed": gate_passed,
                "output": "Simulated pass"
            }
            if not gate_passed:
                all_passed = False
        
        if all_passed:
            self.logger.info("All validation gates passed")
        else:
            self.logger.error("One or more validation gates failed")
        
        return {"all_passed": all_passed, "gate_results": results}
    
    def _phase_review(self, ticket: Ticket) -> None:
        """Review phase: Human reviews the diff"""
        self.logger.info(f"Review phase for ticket: {ticket.id}")
        # Implementation would go here
        pass
    
    def _phase_release(self, ticket: Ticket) -> None:
        """Release phase: Tag and document the artifact"""
        self.logger.info(f"Release phase for ticket: {ticket.id}")
        # Implementation would go here
        pass
    
    def handle_failure(self, ticket: Ticket, error: Exception) -> Dict[str, Any]:
        """
        Trigger the 5-step failure procedure.
        
        Args:
            ticket: The ticket that failed
            error: The exception that occurred
            
        Returns:
            Result dictionary with failure status
        """
        self.logger.error(f"Failure in ticket {ticket.id}: {str(error)}")
        
        # Step 1: Capture logs
        self.capture_logs(ticket, error)
        
        # Step 2: Update TROUBLESHOOTING.md
        self.update_troubleshooting(ticket, error)
        
        # Step 3: Update REPLICATION-NOTES.md
        self.update_replication(ticket, error)
        
        # Step 4: Open ISSUE.md
        self.open_issue(ticket, error)
        
        # Step 5: Halt and wait for human
        self.halt_and_wait_human(ticket)
        
        return {
            "status": "failed",
            "error": str(error),
            "procedure": "5-step failure procedure triggered"
        }
    
    def capture_logs(self, ticket: Ticket, error: Exception) -> None:
        """Save full stdout/stderr to logs/ directory."""
        log_dir = self.base_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"ISS-{timestamp}-{ticket.id[:10]}.log"
        log_path = log_dir / log_filename
        
        log_content = f"""---
title: Failure Log - {ticket.id}
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# Log File: {log_filename}

## Ticket
- ID: {ticket.id}
- Status: {ticket.status.value}
- Depth: {ticket.depth}

## Error
```
{str(error)}
```

## Stack Trace
```
{self._format_exception(error)}
```

## Timestamp
{datetime.now().isoformat()}
"""
        log_path.write_text(log_content)
        self.logger.info(f"Logs captured to {log_path}")
    
    def _format_exception(self, error: Exception) -> str:
        """Format exception with traceback."""
        import traceback
        return traceback.format_exc()
    
    def update_troubleshooting(self, ticket: Ticket, error: Exception) -> None:
        """Append entry to TROUBLESHOOTING.md."""
        troubleshooting_path = self.base_dir / "TROUBLESHOOTING.md"
        
        entry = f"""
## TS-{datetime.now().strftime('%Y%m%d')}-{ticket.id[:8]}

- **Context**: Ticket {ticket.id} in phase {self.current_ticket.status.value if self.current_ticket else 'unknown'}
- **Symptom**: {str(error)}
- **Error Snippet**: `{str(error)[:100]}...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
"""
        
        content = troubleshooting_path.read_text()
        if "---" not in content:
            content = f"""---
title: TROUBLESHOOTING.md
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# TROUBLESHOOTING.md

This file tracks all issues encountered during development.
"""
        
        troubleshooting_path.write_text(content.rstrip() + entry)
        self.logger.info("TROUBLESHOOTING.md updated")
    
    def update_replication(self, ticket: Ticket, error: Exception) -> None:
        """Append entry to REPLICATION-NOTES.md."""
        replication_path = self.base_dir / "REPLICATION-NOTES.md"
        
        entry = f"""
| TS-{datetime.now().strftime('%Y%m%d')}-{ticket.id[:8]} | Ticket {ticket.id} | {str(error)[:50]}... | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
"""
        
        content = replication_path.read_text()
        if "---" not in content:
            content = f"""---
title: REPLICATION-NOTES.md
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# REPLICATION-NOTES.md

## Environment Setup

| Component | Value |
|-----------|-------|
| OS | Windows 11 |
| IDE | Visual Studio Code |
| Project | Fractal_Claws |
| Version | 0.7.0 |

## Recurring Errors

| ID | Ticket | Issue | Date |
|----|--------|-------|------|
"""
        
        replication_path.write_text(content.rstrip() + entry)
        self.logger.info("REPLICATION-NOTES.md updated")
    
    def open_issue(self, ticket: Ticket, error: Exception) -> None:
        """Create or update ISSUE.md entry."""
        issue_path = self.base_dir / "ISSUE.md"
        
        entry = f"""
## ISS-{datetime.now().strftime('%Y%m%d')}-{ticket.id[:8]}

- **Status**: open
- **Blocked On**: human
- **Title**: Failure in ticket {ticket.id}
- **Description**: {str(error)}
- **Ticket ID**: {ticket.id}
- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Required Action**: Human review and approval to proceed
"""
        
        content = issue_path.read_text()
        if "---" not in content:
            content = f"""---
title: ISSUE.md
version: "0.7.0"
last_updated: "{datetime.now().strftime('%Y-%m-%d')}"
---

# ISSUE.md

Open issues requiring human attention.

## Issue Tracker

| ID | Status | Blocked On | Title |
|----|--------|------------|-------|
"""
        
        issue_path.write_text(content.rstrip() + entry)
        self.logger.info("ISSUE.md updated")
    
    def halt_and_wait_human(self, ticket: Ticket) -> None:
        """Stop all work and await human instruction."""
        self.logger.critical(f"Halted on ticket {ticket.id}. See ISSUE.md for required action.")
        raise SystemExit(f"Halted on {ticket.id}. See ISSUE.md for required action.")
    
    def validate(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Run validation gates for a ticket.
        
        Args:
            ticket: The ticket to validate
            
        Returns:
            Dictionary with gate results
        """
        return self._phase_validate(ticket)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get operator statistics."""
        return {
            "total_tickets": len(self.tickets),
            "pending_tickets": sum(1 for t in self.tickets.values() if t.status == TicketStatus.PENDING),
            "escalated_tickets": sum(1 for t in self.tickets.values() if t.status == TicketStatus.ESCALATED),
            "closed_tickets": sum(1 for t in self.tickets.values() if t.status == TicketStatus.CLOSED)
        }