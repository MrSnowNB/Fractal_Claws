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
