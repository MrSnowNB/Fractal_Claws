"""
test_step09_schema_slots.py — Round-trip tests for graph_scope and return_to

STEP-09 fix: ticket_io.load_ticket() was silently dropping graph_scope and
return_to because neither field appeared in the Ticket() constructor call
or in _DEFAULTS. These tests verify that both fields survive the full
load → to_dict → from_dict round-trip and are correctly hydrated to None
when absent from YAML.

Added to the global test suite as part of STEP-11 Definition of Done:
  pytest tests/test_ticket_io.py -v -k 'graph_scope or return_to'
"""

import os
import tempfile
import pytest
import yaml

from src.ticket_io import load_ticket
from src.operator_v7 import Ticket


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _write_ticket(tmp_dir: str, data: dict) -> str:
    path = os.path.join(tmp_dir, f"{data['ticket_id']}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    return path


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGraphScopeRoundTrip:
    """graph_scope: dict | None — must survive load_ticket() without data loss."""

    def test_graph_scope_none_when_absent(self, tmp_path):
        """A ticket YAML with no graph_scope field loads with graph_scope=None."""
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-GS-001",
            "title": "no graph_scope",
            "task": "placeholder task",
        })
        ticket = load_ticket(path)
        assert ticket.graph_scope is None, (
            f"Expected graph_scope=None, got {ticket.graph_scope!r}"
        )

    def test_graph_scope_dict_survives_load(self, tmp_path):
        """A ticket YAML with a graph_scope dict is fully hydrated by load_ticket()."""
        gs = {"scope": "local", "nodes": ["STEP-10", "STEP-11"], "depth": 2}
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-GS-002",
            "title": "with graph_scope",
            "task": "placeholder task",
            "graph_scope": gs,
        })
        ticket = load_ticket(path)
        assert ticket.graph_scope == gs, (
            f"graph_scope not preserved by load_ticket(): got {ticket.graph_scope!r}"
        )

    def test_graph_scope_round_trips_through_to_dict(self, tmp_path):
        """graph_scope survives Ticket.to_dict() → Ticket.from_dict() round-trip."""
        gs = {"scope": "global", "parent_ticket": "STEP-11"}
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-GS-003",
            "title": "round-trip graph_scope",
            "task": "placeholder task",
            "graph_scope": gs,
        })
        ticket = load_ticket(path)
        d = ticket.to_dict()
        assert d["graph_scope"] == gs, (
            f"graph_scope lost in to_dict(): got {d.get('graph_scope')!r}"
        )
        ticket2 = Ticket.from_dict(d)
        assert ticket2.graph_scope == gs, (
            f"graph_scope lost in from_dict(): got {ticket2.graph_scope!r}"
        )


class TestReturnToRoundTrip:
    """return_to: str | None — must survive load_ticket() without data loss."""

    def test_return_to_none_when_absent(self, tmp_path):
        """A ticket YAML with no return_to field loads with return_to=None."""
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-RT-001",
            "title": "no return_to",
            "task": "placeholder task",
        })
        ticket = load_ticket(path)
        assert ticket.return_to is None, (
            f"Expected return_to=None, got {ticket.return_to!r}"
        )

    def test_return_to_string_survives_load(self, tmp_path):
        """A ticket YAML with return_to set is fully hydrated by load_ticket()."""
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-RT-002",
            "title": "with return_to",
            "task": "placeholder task",
            "return_to": "STEP-11-ORCHESTRATOR",
        })
        ticket = load_ticket(path)
        assert ticket.return_to == "STEP-11-ORCHESTRATOR", (
            f"return_to not preserved by load_ticket(): got {ticket.return_to!r}"
        )

    def test_return_to_round_trips_through_to_dict(self, tmp_path):
        """return_to survives Ticket.to_dict() → Ticket.from_dict() round-trip."""
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-RT-003",
            "title": "round-trip return_to",
            "task": "placeholder task",
            "return_to": "luffy-v1-parent",
        })
        ticket = load_ticket(path)
        d = ticket.to_dict()
        assert d["return_to"] == "luffy-v1-parent", (
            f"return_to lost in to_dict(): got {d.get('return_to')!r}"
        )
        ticket2 = Ticket.from_dict(d)
        assert ticket2.return_to == "luffy-v1-parent", (
            f"return_to lost in from_dict(): got {ticket2.return_to!r}"
        )

    def test_both_fields_none_is_lossless(self, tmp_path):
        """A ticket with both graph_scope=None and return_to=None round-trips cleanly."""
        path = _write_ticket(str(tmp_path), {
            "ticket_id": "TEST-BOTH-NULL",
            "title": "both null",
            "task": "placeholder task",
            "graph_scope": None,
            "return_to": None,
        })
        ticket = load_ticket(path)
        d = ticket.to_dict()
        t2 = Ticket.from_dict(d)
        assert t2.graph_scope is None
        assert t2.return_to is None
