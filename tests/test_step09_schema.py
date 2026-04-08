"""
test_step09_schema.py — STEP-09-F: append_journal agent_id validation

Gate: Every journal record must have agent_id present (default or custom).
"""

import json
import pytest
from scripts.log_journal import append_journal


class TestAppendJournalAgentId:
    """STEP-09-F: Verify agent_id handling in append_journal()."""

    def test_default_agent_id_is_luffy_v1(self, tmp_path):
        """append_journal() writes records with agent_id='luffy-v1' by default."""
        # Use temp dir journal file
        log_path = str(tmp_path / "luffy-journal.jsonl")

        record = {"step": "test", "action": "test_action", "status": "success"}
        append_journal(record)

        # Read from default logs path (since function writes there)
        with open("logs/luffy-journal.jsonl", "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["agent_id"] == "luffy-v1"

    def test_custom_agent_id_preserved(self, tmp_path):
        """append_journal() preserves custom agent_id when passed."""
        record = {"step": "test", "action": "custom_action", "status": "ok"}
        append_journal(record, agent_id="custom-bot-v2")

        with open("logs/luffy-journal.jsonl", "r", encoding="utf-8") as f:
            lines = f.readlines()

        data = json.loads(lines[-1])
        assert data["agent_id"] == "custom-bot-v2"

    def test_multiple_records_all_have_agent_id(self, tmp_path):
        """Multiple append_journal calls all produce records with agent_id."""
        append_journal({"step": "a"})
        append_journal({"step": "b"}, agent_id="alt-agent")
        append_journal({"step": "c"})

        with open("logs/luffy-journal.jsonl", "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) >= 3
        for line in lines[-3:]:
            data = json.loads(line)
            assert "agent_id" in data
            assert data["agent_id"] is not None
