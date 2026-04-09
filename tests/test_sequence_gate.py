"""tests/test_sequence_gate.py — Sequence gate (journal + commit enforcement) tests.

All tests use tmp_path and mock subprocess. No actual git operations.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.sequence_gate import SequenceGate


# ── sequence_start ────────────────────────────────────────────────────────────

class TestSequenceStart:
    def test_start_allowed_fresh(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(journal_path=str(journal))
        ok, reason = gate.sequence_start("STEP-10-A")
        assert ok is True
        assert "STEP-10-A" in reason

    def test_start_blocked_with_pending_commit(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(journal_path=str(journal))
        gate._pending_commit = True
        gate._current_step = "STEP-09-F"

        ok, reason = gate.sequence_start("STEP-10-A")
        assert ok is False
        assert "BLOCKED" in reason
        assert "STEP-09-F" in reason

    def test_start_allowed_when_enforcement_disabled(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(
            journal_path=str(journal),
            enforce_commit=False,
        )
        gate._pending_commit = True
        gate._current_step = "STEP-09-F"

        ok, reason = gate.sequence_start("STEP-10-A")
        assert ok is True


# ── sequence_checkpoint ───────────────────────────────────────────────────────

class TestSequenceCheckpoint:
    @patch("agent.sequence_gate.subprocess.run")
    def test_checkpoint_writes_journal(self, mock_run, tmp_path):
        journal = tmp_path / "journal.jsonl"
        # Mock git add + commit success
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        gate = SequenceGate(journal_path=str(journal))
        result = gate.sequence_checkpoint(
            "STEP-10-A",
            files_changed=["agent/runner.py"],
            summary="Wired context budget into drain loop",
        )

        assert result["journal_ok"] is True
        assert journal.exists()
        lines = journal.read_text().strip().split("\n")
        entry = json.loads(lines[-1])
        assert entry["step"] == "STEP-10-A"
        assert entry["agent_id"] == "luffy-v1"
        assert "Wired context budget" in entry["action"]

    @patch("agent.sequence_gate.subprocess.run")
    def test_checkpoint_creates_commit(self, mock_run, tmp_path):
        journal = tmp_path / "journal.jsonl"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        gate = SequenceGate(journal_path=str(journal))
        result = gate.sequence_checkpoint(
            "STEP-10-A",
            files_changed=["agent/runner.py", "settings.yaml"],
            summary="Context budget wiring",
        )

        assert result["commit_ok"] is True
        assert "STEP-10-A" in result["commit_msg"]
        # git add called for each file + journal
        assert mock_run.call_count >= 3  # 2 files + journal + commit

    @patch("agent.sequence_gate.subprocess.run")
    def test_checkpoint_commit_failure_sets_pending(self, mock_run, tmp_path):
        journal = tmp_path / "journal.jsonl"
        # git add succeeds, git commit fails
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add file
            MagicMock(returncode=0),  # git add journal
            MagicMock(returncode=1, stderr="nothing to commit"),  # git commit
        ]

        gate = SequenceGate(journal_path=str(journal))
        result = gate.sequence_checkpoint(
            "STEP-10-A",
            files_changed=["agent/runner.py"],
            summary="test",
        )

        assert result["commit_ok"] is False
        assert gate._pending_commit is True


# ── sequence_complete ─────────────────────────────────────────────────────────

class TestSequenceComplete:
    def test_complete_unlocks_next_sequence(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(journal_path=str(journal))
        gate._pending_commit = True
        gate._current_step = "STEP-10-A"

        gate.sequence_complete("STEP-10-A")
        assert gate._pending_commit is False
        assert gate._current_step is None
        assert "STEP-10-A" in gate.completed

    def test_complete_allows_new_start(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(journal_path=str(journal))
        gate.sequence_complete("STEP-10-A")

        ok, _ = gate.sequence_start("STEP-10-B")
        assert ok is True


# ── has_pending_work ──────────────────────────────────────────────────────────

class TestHasPendingWork:
    def test_no_pending_work_initially(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(journal_path=str(journal))
        pending, step = gate.has_pending_work()
        assert pending is False
        assert step is None

    def test_reports_pending_correctly(self, tmp_path):
        journal = tmp_path / "journal.jsonl"
        gate = SequenceGate(journal_path=str(journal))
        gate._pending_commit = True
        gate._current_step = "STEP-10-A"

        pending, step = gate.has_pending_work()
        assert pending is True
        assert step == "STEP-10-A"
