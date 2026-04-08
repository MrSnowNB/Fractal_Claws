"""
Fractal_Claws Package

This package implements the self-healing recursive first principles problem solver.
"""

__version__ = "0.7.0"
__author__ = "MrSnowNB"

# Expose core types from operator_v7 for backward compatibility
from src.operator_v7 import (
    Operator,
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketDepth,
)

__all__ = [
    "Operator",
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "TicketDepth",
]