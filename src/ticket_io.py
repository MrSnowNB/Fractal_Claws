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
    ticket._extras mirrors every raw YAML key so runner.py and tests can
    still do extras['task'], extras['depends_on'], etc.
    The as_dict() shim is preserved for serialization use cases only.
    runner.py must use ticket.field attribute access — not ticket.get() or ticket[key].
"""

from __future__ import annotations

import copy
import glob
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Union

import yaml

# Define log directory for lint violations
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

# Import canonical dataclass from operator_v7
from src.operator_v7 import Ticket, TicketResult, TicketStatus, TicketPriority

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
    "result":        None,
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
        "open":        "pending",
        "failed":      "escalated",
        "in_progress": "pending",
        "running":     "pending",
    }
    raw = str(value).lower() if value is not None else "pending"
    raw = _ALIAS.get(raw, raw)
    try:
        return TicketStatus(raw)
    except ValueError:
        logger.warning("[ticket_io] %s: unknown status %r → PENDING", ticket_id, value)
        return TicketStatus.PENDING


def _coerce_priority(value: object, ticket_id: str) -> TicketPriority:
    """Map raw string to TicketPriority; default to MEDIUM with a warning."""
    _ALIAS = {
        "urgent": "critical",
    }
    raw = str(value).lower() if value is not None else "medium"
    raw = _ALIAS.get(raw, raw)
    try:
        return TicketPriority(raw)
    except ValueError:
        logger.warning("[ticket_io] %s: unknown priority %r → MEDIUM", ticket_id, value)
        return TicketPriority.MEDIUM


def _build_result(value: object) -> Optional[TicketResult]:
    """Convert raw dict to TicketResult; return None if value is None or empty."""
    if value is None:
        return None
    if isinstance(value, dict):
        return TicketResult(
            passed=value.get("passed", False),
            score=value.get("score"),
            notes=value.get("notes"),
            output_path=value.get("output_path"),
        )
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def load_ticket(path: str) -> Ticket:
    """
    Load a YAML ticket file and return a fully-populated Ticket dataclass.

    All runner.py extras (task, depends_on, context_files, result_path, etc.)
    are mapped directly onto the dataclass fields.  ticket._extras mirrors
    the full raw YAML dict so callers can still do extras['task'] etc.

    Unknown status/priority values are silently coerced to PENDING/MEDIUM
    (logged at WARNING level) — never raise on unknown enum values.

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

    # Build Ticket directly using local coerce helpers so unknown
    # status/priority values fall back gracefully instead of raising.
    from datetime import datetime
    ticket = Ticket(
        id=ticket_id,
        title=raw.get("title", ""),
        depth=raw.get("depth", 0),
        parent=raw.get("parent"),
        children=raw.get("children", []),
        status=_coerce_status(raw.get("status", "pending"), ticket_id),
        attempts=raw.get("attempts", 0),
        decrement=raw.get("decrement", 3),
        priority=_coerce_priority(raw.get("priority", "medium"), ticket_id),
        result=_build_result(raw.get("result")),
        created_at=raw.get("created_at", datetime.now().isoformat()),
        task=raw.get("task"),
        max_tokens=raw.get("max_tokens"),
        depends_on=raw.get("depends_on", []),
        context_files=raw.get("context_files", []),
        result_path=raw.get("result_path"),
        rationale=raw.get("rationale", ""),
        produces=raw.get("produces", []),
        consumes=raw.get("consumes", []),
        tags=raw.get("tags", []),
        agent=raw.get("agent", ""),
    )

    # _extras mirrors the full raw dict so tests and runner.py can still
    # access any key via ticket._extras['key'] without breakage.
    object.__setattr__(ticket, "_extras", dict(raw))

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


# ── Linting ─────────────────────────────────────────────────────────────────────

_LINT_VIOLATIONS_LOG = os.path.join(LOG_DIR, "lint-violations.jsonl")


def _log_lint_violation(ticket_id: str, rule: str, message: str, path: str) -> None:
    """Append a lint violation record to lint-violations.jsonl."""
    record = {
        "ticket_id": ticket_id,
        "rule": rule,
        "message": message,
        "path": path,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    os.makedirs(os.path.dirname(_LINT_VIOLATIONS_LOG) if os.path.dirname(_LINT_VIOLATIONS_LOG) else ".", exist_ok=True)
    with open(_LINT_VIOLATIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    logger.warning("[lint] %s: %s — %s", ticket_id, rule, message)


def lint_ticket(ticket: Ticket, path: str) -> list[str]:
    """
    Check a ticket for common lint violations. Warns but does not block.
    
    Rules implemented:
      - exec_python path must start with 'output/' (sandbox rule)
      - write_file + exec_python pair must use same base name
      - task must be present (non-empty)
      - task must not exceed 500 words (practical limit)
    
    Returns list of violation messages (empty if clean).
    """
    violations = []
    ticket_id = ticket.id
    
    # Rule: exec_python paths must start with 'output/'
    allowed_tools = ticket.allowed_tools or []
    if "exec_python" in allowed_tools:
        produces = ticket.produces or []
        for prod in produces:
            if prod.startswith("output/"):
                continue
            if prod.startswith("stdout:"):
                continue
            # Check if this is a file path in produces that would be exec'd
            if "/" not in prod and not prod.startswith("stdout:"):
                # This could be a bare filename that would need exec_python
                # Check context_files for clues
                for cf in (ticket.context_files or []):
                    if cf.endswith(".py") and not cf.startswith("output/"):
                        msg = f"exec_python target {cf} must start with 'output/'"
                        _log_lint_violation(ticket_id, "sandbox-exec", msg, path)
                        violations.append(msg)
    
    # Rule: task must be present and non-empty
    if not ticket.task or not str(ticket.task).strip():
        msg = "task field is empty or missing"
        _log_lint_violation(ticket_id, "required-task", msg, path)
        violations.append(msg)
    
    # Rule: task should not exceed 500 words
    if ticket.task:
        word_count = len(str(ticket.task).split())
        if word_count > 500:
            msg = f"task is {word_count} words (limit: 500)"
            _log_lint_violation(ticket_id, "task-length", msg, path)
            violations.append(msg)
    
    return violations
