"""
ticket_io.py — Typed Ticket I/O bridge for Fractal Claws

Bridges runner.py's raw-dict YAML loading with operator_v7.py's typed
Ticket dataclass. All persistence stays YAML on disk — this module adds
schema validation and type coercion at the read/write boundary.

Public API
----------
    load_ticket(path)           -> Ticket       (replaces runner raw dict load)
    save_ticket(path, ticket)   -> None         (accepts Ticket OR dict)
    move_ticket(src, dst_dir)   -> str          (returns new path)
    scan_dir(directory)         -> list[Ticket] (sorted by ticket_id)
    ticket_exists(ticket_id, directory) -> bool

All functions raise TicketIOError on unrecoverable schema violations.
ValidationWarning is logged (not raised) for non-critical field coercions.

Backward compatibility
----------------------
    load_ticket() returns a Ticket dataclass with all fields populated.
    The as_dict() shim is preserved for serialization use cases only.
    runner.py must use ticket.field attribute access — not ticket.get() or ticket[key].
"""

from __future__ import annotations

import copy
import glob
import logging
import os
import time
from pathlib import Path
from typing import Union

import yaml

# Import canonical dataclass from operator_v7
from src.operator_v7 import Ticket, TicketStatus, TicketPriority

logger = logging.getLogger(__name__)


# ── Exceptions ────────────────────────────────────────────────────────────────

class TicketIOError(Exception):
    """Raised when a ticket file cannot be parsed or written."""


class ValidationWarning(UserWarning):
    """Issued when a field is coerced to a default during load."""


# ── Required fields ───────────────────────────────────────────────────────────

# Fields that MUST exist in a valid ticket YAML.
_REQUIRED_FIELDS: frozenset[str] = frozenset({"ticket_id"})

# Fields filled with safe defaults if absent (backward compat).
_DEFAULTS: dict = {
    "depth":         0,
    "parent":        None,
    "children":      [],
    "status":        "pending",
    "attempts":      0,
    "decrement":     3,
    "priority":      "medium",
    "result":        {},
    "title":         "",
    "task":          "",
    "rationale":     "",
    "produces":      [],
    "consumes":      [],
    "tags":          [],
    "depends_on":    [],
    "allowed_tools": [],
    "agent":         "",
    "result_path":   "",
    "context_files": [],
    "max_tokens":    None,
    "max_depth":     2,
}


# ── YAML helpers ──────────────────────────────────────────────────────────────

def _read_yaml(path: str) -> dict:
    """
    Read a YAML file that may contain one or two documents.
    Two-document tickets (legacy runner format) are merged: doc[0] base,
    doc[1] overlay.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            docs = list(yaml.safe_load_all(fh))
    except FileNotFoundError:
        raise TicketIOError(f"ticket not found: {path}")
    except yaml.YAMLError as exc:
        raise TicketIOError(f"YAML parse error in {path}: {exc}") from exc

    if not docs or docs[0] is None:
        raise TicketIOError(f"empty ticket file: {path}")

    if len(docs) >= 2:
        merged = dict(docs[0] or {})
        merged.update(docs[1] or {})
        return merged

    return dict(docs[0])


def _write_yaml(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, sort_keys=False)


# ── Coercion helpers ──────────────────────────────────────────────────────────

def _coerce_status(value: object, ticket_id: str) -> TicketStatus:
    """Map raw string to TicketStatus; default to PENDING with a warning."""
    _ALIAS = {
        "open":   "pending",
        "failed": "escalated",
    }
    raw = str(value).lower() if value is not None else "pending"
    raw = _ALIAS.get(raw, raw)
    try:
        return TicketStatus(raw)
    except ValueError:
        logger.warning("[ticket_io] %s: unknown status %r → PENDING", ticket_id, value)
        return TicketStatus.PENDING


def _coerce_priority(value: object, ticket_id: str) -> TicketPriority:
    raw = str(value).lower() if value is not None else "medium"
    try:
        return TicketPriority(raw)
    except ValueError:
        logger.warning("[ticket_io] %s: unknown priority %r → MEDIUM", ticket_id, value)
        return TicketPriority.MEDIUM


# ── Public API ────────────────────────────────────────────────────────────────

def load_ticket(path: str) -> Ticket:
    """
    Load a YAML ticket file and return a fully-populated Ticket dataclass.

    All runner.py extras (task, depends_on, context_files, result_path, etc.)
    are mapped directly onto the dataclass fields — no _extras side-channel.

    Raises
    ------
    TicketIOError
        If the file is missing, unparseable, or lacks required fields.
    """
    raw = _read_yaml(path)

    # Validate required fields
    for fld in _REQUIRED_FIELDS:
        if fld not in raw or raw[fld] is None:
            raise TicketIOError(f"missing required field '{fld}' in {path}")

    ticket_id = str(raw["ticket_id"])

    # Apply defaults for any absent optional fields (non-destructive)
    for key, default in _DEFAULTS.items():
        if key not in raw:
            raw[key] = copy.deepcopy(default)
            logger.debug("[ticket_io] %s: defaulted %s=%r", ticket_id, key, default)

    # Use Ticket.from_dict() which maps all fields including Step-5 extras.
    # from_dict() accepts both 'ticket_id' and 'id' keys.
    ticket = Ticket.from_dict(raw)

    # Preserve legacy round-trip fields not on the dataclass (updated_at, attempts_log).
    _LEGACY_EXTRAS = ["updated_at", "attempts_log", "allowed_tools", "max_depth"]
    extras: dict = {k: raw[k] for k in _LEGACY_EXTRAS if k in raw}
    if extras:
        object.__setattr__(ticket, "_extras", extras)

    return ticket


def save_ticket(path: str, ticket: Union[Ticket, dict]) -> None:
    """
    Write a ticket to YAML.  Accepts either a typed Ticket or a raw dict
    (backward compat with runner.py callers not yet migrated).
    """
    if isinstance(ticket, Ticket):
        data = ticket.to_dict()
        # Re-inject legacy extras so the YAML stays complete
        extras = getattr(ticket, "_extras", {})
        data.update(extras)
        # Status alias: runner.py open_dir expects "open" not "pending"
        if data.get("status") == "pending":
            data["status"] = "open"
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        data = dict(ticket)

    _write_yaml(path, data)


def as_dict(ticket: Union[Ticket, dict]) -> dict:
    """
    Return a plain dict regardless of input type.
    Retained for serialization use cases only — do NOT use for read access in runner.py.
    """
    if isinstance(ticket, Ticket):
        data = ticket.to_dict()
        extras = getattr(ticket, "_extras", {})
        data.update(extras)
        if "ticket_id" in data and "id" not in data:
            data["id"] = data["ticket_id"]
        if data.get("status") == "pending":
            data["status"] = "open"
        return data
    return ticket


def move_ticket(src: str, dst_dir: str) -> str:
    """
    Move a ticket YAML from src path to dst_dir.
    Returns the new full path.
    Raises TicketIOError if src does not exist.
    """
    if not os.path.exists(src):
        raise TicketIOError(f"cannot move — source not found: {src}")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    import shutil
    shutil.move(src, dst)
    return dst


def scan_dir(directory: str) -> list[Ticket]:
    """
    Load all *.yaml files in directory as Ticket objects, sorted by ticket_id.
    Files that fail validation are logged and skipped (not raised).
    """
    paths = sorted(glob.glob(os.path.join(directory, "*.yaml")))
    tickets: list[Ticket] = []
    for path in paths:
        try:
            tickets.append(load_ticket(path))
        except TicketIOError as exc:
            logger.warning("[ticket_io] skipping %s: %s", path, exc)
    return tickets


def ticket_exists(ticket_id: str, directory: str) -> bool:
    """Return True if <directory>/<ticket_id>.yaml exists on disk."""
    return os.path.exists(os.path.join(directory, f"{ticket_id}.yaml"))
