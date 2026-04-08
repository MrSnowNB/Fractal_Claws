"""
delegate_task.py — Shared-filesystem ticket transport for Fractal Claws

This module provides delegate_task() — the ONLY function with transport
logic. All other modules (runner.py, operator_v7.py) must NOT contain
filesystem transport code.

The transport model is shared filesystem: tickets are written to disk,
then the child agent reads them from the open/ directory.

Public API
----------
    delegate_task(ticket, open_dir, closed_dir) -> str
        Write ticket to open_dir/<ticket_id>.yaml, return result_path

Invariants
----------
    - No subprocesses, no network calls, no external dependencies
    - No transport logic in runner.py or operator_v7.py
    - All ticket I/O goes through ticket_io.py or this module
"""

from __future__ import annotations

import os
import time

from src.operator_v7 import Ticket
from src.ticket_io import save_ticket


def delegate_task(ticket: Ticket, open_dir: str, closed_dir: str) -> str:
    """
    Write a ticket to the shared open directory for child processing.
    
    The transport model is filesystem-based:
      1. Write ticket to open_dir/<ticket_id>.yaml
      2. Child agent polls open_dir for new tickets
      3. Child writes result to closed_dir/<ticket_id>.yaml
      4. Parent reads result from closed_dir/<ticket_id>.yaml
    
    Args
    ----
        ticket: Typed Ticket dataclass
        open_dir: Directory where tickets are placed for child consumption
        closed_dir: Directory where child writes completed results
    
    Returns
    -------
        result_path: Path where child will write the result YAML
    
    Raises
    ------
        OSError: If directory creation fails
    """
    # Ensure directories exist (shared filesystem requirement)
    os.makedirs(open_dir, exist_ok=True)
    os.makedirs(closed_dir, exist_ok=True)

    # Ticket path in open directory
    ticket_path = os.path.join(open_dir, f"{ticket.id}.yaml")

    # Result path — child writes here after processing
    result_path = os.path.join(closed_dir, f"{ticket.id}.yaml")

    # Write ticket to open directory (child will read this)
    save_ticket(ticket_path, ticket)

    # Log for audit trail
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(os.path.join(open_dir, ".audit.log"), "a", encoding="utf-8") as f:
        f.write(f"{ts} | delegate | {ticket.id} | {ticket_path}\n")

    return result_path