"""tests/test_context_budget.py — Context budget manager tests.

All tests use tmp_path only. No network, no model, no endpoint required.
"""

import json
import time
from pathlib import Path

import pytest

from agent.context_budget import ContextBudget, DEFAULT_CTX_LIMIT, CHARS_PER_TOKEN


# ── file_hash ─────────────────────────────────────────────────────────────────

class TestFileHash:
    def test_hash_deterministic(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello world")
        h1 = ContextBudget.file_hash(str(f))
        h2 = ContextBudget.file_hash(str(f))
        assert h1 == h2

    def test_hash_changes_on_content_change(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("version 1")
        h1 = ContextBudget.file_hash(str(f))
        f.write_text("version 2")
        h2 = ContextBudget.file_hash(str(f))
        assert h1 != h2


# ── estimate_tokens ───────────────────────────────────────────────────────────

class TestEstimateTokens:
    def test_empty_string(self):
        assert ContextBudget.estimate_tokens("") == 1  # min 1

    def test_known_length(self):
        text = "a" * 350  # 350 chars / 3.5 = 100 tokens
        assert ContextBudget.estimate_tokens(text) == 100


# ── should_read ───────────────────────────────────────────────────────────────

class TestShouldRead:
    def test_new_file_should_read(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("# Step 8 spec\n" * 10)

        budget = ContextBudget(cache_path=str(cache))
        should, reason = budget.should_read(str(f))
        assert should is True
        assert reason == "new"

    def test_cached_file_should_not_read(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("# Step 8 spec\n" * 10)

        budget = ContextBudget(cache_path=str(cache))
        budget.should_read(str(f))
        budget.mark_read(str(f))
        # Second check — same session, same content
        should, reason = budget.should_read(str(f))
        assert should is False
        assert reason == "cached"

    def test_changed_file_should_read(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("version 1")

        budget = ContextBudget(cache_path=str(cache))
        budget.mark_read(str(f))
        # Change the file
        f.write_text("version 2 with more content")
        should, reason = budget.should_read(str(f))
        assert should is True
        assert reason == "changed"

    def test_missing_file_returns_false(self, tmp_path):
        cache = tmp_path / "cache.json"
        budget = ContextBudget(cache_path=str(cache))
        should, reason = budget.should_read(str(tmp_path / "nonexistent.md"))
        assert should is False
        assert reason == "missing"

    def test_budget_exceeded_blocks_read(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "big.md"
        # Create a file that's ~25K tokens (87.5K chars)
        f.write_text("x" * 87500)

        budget = ContextBudget(
            cache_path=str(cache),
            zones={"docs_cache": 1000},  # tiny budget
        )
        should, reason = budget.should_read(str(f), zone="docs_cache")
        assert should is False
        assert reason == "budget_exceeded"


# ── mark_read ─────────────────────────────────────────────────────────────────

class TestMarkRead:
    def test_mark_read_updates_cache_file(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("hello world")

        budget = ContextBudget(cache_path=str(cache))
        tokens = budget.mark_read(str(f))

        assert tokens > 0
        assert cache.exists()
        data = json.loads(cache.read_text())
        assert str(f.resolve()) in data["hashes"]

    def test_mark_read_tracks_zone_usage(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("a" * 350)  # ~100 tokens

        budget = ContextBudget(cache_path=str(cache))
        budget.mark_read(str(f), zone="docs_cache")
        assert budget._zone_usage["docs_cache"] == 100


# ── budget_report ─────────────────────────────────────────────────────────────

class TestBudgetReport:
    def test_report_has_all_zones(self, tmp_path):
        cache = tmp_path / "cache.json"
        budget = ContextBudget(cache_path=str(cache))
        report = budget.budget_report()
        assert "docs_cache" in report
        assert "ticket_context" in report
        assert "total" in report

    def test_report_sums_correctly(self, tmp_path):
        cache = tmp_path / "cache.json"
        f1 = tmp_path / "a.md"
        f1.write_text("a" * 350)  # ~100 tokens
        f2 = tmp_path / "b.md"
        f2.write_text("b" * 700)  # ~200 tokens

        budget = ContextBudget(cache_path=str(cache))
        budget.mark_read(str(f1), zone="docs_cache")
        budget.mark_read(str(f2), zone="ticket_context")

        report = budget.budget_report()
        assert report["docs_cache"]["used"] == 100
        assert report["ticket_context"]["used"] == 200
        assert report["total"]["used"] == 300


# ── get_read_summary ──────────────────────────────────────────────────────────

class TestGetReadSummary:
    def test_returns_none_for_unread_file(self, tmp_path):
        cache = tmp_path / "cache.json"
        budget = ContextBudget(cache_path=str(cache))
        assert budget.get_read_summary("/some/path") is None

    def test_returns_summary_for_cached_file(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("hello world")

        budget = ContextBudget(cache_path=str(cache))
        budget.mark_read(str(f))
        summary = budget.get_read_summary(str(f))
        assert summary is not None
        assert "cached" in summary
        assert "tokens" in summary
        assert "hash=" in summary


# ── reset_session ─────────────────────────────────────────────────────────────

class TestResetSession:
    def test_clears_session_tracking(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("hello")

        budget = ContextBudget(cache_path=str(cache))
        budget.mark_read(str(f))
        assert len(budget._session_reads) == 1
        assert budget._zone_usage["docs_cache"] > 0

        budget.reset_session()
        assert len(budget._session_reads) == 0
        assert budget._zone_usage["docs_cache"] == 0

    def test_reset_preserves_persistent_cache(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("hello")

        budget = ContextBudget(cache_path=str(cache))
        budget.mark_read(str(f))
        resolved = str(f.resolve())
        assert resolved in budget._file_hashes

        budget.reset_session()
        # Hashes persist — only session tracking resets
        assert resolved in budget._file_hashes


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_cache_survives_reload(self, tmp_path):
        cache = tmp_path / "cache.json"
        f = tmp_path / "doc.md"
        f.write_text("persistent data")

        budget1 = ContextBudget(cache_path=str(cache))
        budget1.mark_read(str(f))
        h1 = budget1._file_hashes[str(f.resolve())]

        # New instance loads from same cache
        budget2 = ContextBudget(cache_path=str(cache))
        assert str(f.resolve()) in budget2._file_hashes
        assert budget2._file_hashes[str(f.resolve())] == h1
