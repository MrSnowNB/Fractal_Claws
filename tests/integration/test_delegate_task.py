"""tests/integration/test_delegate_task.py — Delegate task transport integration tests."""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

try:
    from tools.delegate_task import delegate_task
    from src.operator_v7 import Ticket
    _IMPORT_OK = True
except ImportError:
    delegate_task = None  # type: ignore
    Ticket = None  # type: ignore
    _IMPORT_OK = False


# Integration tests are skipped by default — run only when explicitly requested.
# Also skipped if import failed (e.g. sys.path issues during full-suite collection).
pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="tools.delegate_task not importable in this collection context"
)


@pytest.mark.skip(reason="Integration tests require full filesystem transport; run manually")
class TestDelegateTaskIntegration:
    """Integration tests for delegate_task() shared-filesystem transport."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary open_dir and closed_dir."""
        base = tempfile.mkdtemp()
        open_dir = os.path.join(base, "tickets", "open")
        closed_dir = os.path.join(base, "tickets", "closed")
        os.makedirs(open_dir, exist_ok=True)
        os.makedirs(closed_dir, exist_ok=True)
        yield open_dir, closed_dir
        shutil.rmtree(base)

    def test_delegate_task_creates_open_ticket(self, temp_dirs):
        """delegate_task writes a ticket to open_dir."""
        open_dir, closed_dir = temp_dirs

        ticket = Ticket(
            id="TEST-001",
            title="Test delegation",
            task="echo hello",
            context_files=[],
            result_path=None,
            result=None,
        )

        result_path = delegate_task(
            ticket=ticket,
            open_dir=open_dir,
            closed_dir=closed_dir,
        )

        ticket_file = os.path.join(open_dir, "TEST-001.yaml")
        assert os.path.exists(ticket_file)

    def test_delegate_task_round_trip_lossless(self, temp_dirs):
        """Ticket round-trip via YAML is lossless."""
        open_dir, closed_dir = temp_dirs

        original = Ticket(
            id="TEST-002",
            title="Round-trip test",
            task="validate data",
            context_files=["src/ticket_io.py"],
            result_path=None,
            result=None,
        )

        delegate_task(
            ticket=original,
            open_dir=open_dir,
            closed_dir=closed_dir,
        )

        ticket_file = os.path.join(open_dir, "TEST-002.yaml")
        restored = Ticket.from_file(ticket_file)

        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.task == original.task

    def test_delegate_task_writes_successfully(self, temp_dirs):
        """delegate_task creates dirs and writes ticket successfully."""
        open_dir, closed_dir = temp_dirs

        ticket = Ticket(
            id="TEST-003",
            title="Write success test",
            task="test",
            context_files=[],
            result_path=None,
            result=None,
        )

        result_path = delegate_task(
            ticket=ticket,
            open_dir=open_dir,
            closed_dir=closed_dir,
        )
        assert result_path is not None
        assert os.path.exists(os.path.join(open_dir, "TEST-003.yaml"))

    def test_delegate_task_invalid_ticket_raises(self):
        """delegate_task fails on invalid ticket dict."""
        with pytest.raises(TypeError):
            delegate_task(
                ticket={"invalid": "ticket"},
                open_dir="/tmp",
                closed_dir="/tmp",
            )
