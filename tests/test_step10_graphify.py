#!/usr/bin/env python3
"""test_step10_graphify.py — pytest tests for ContextBudget.graphify_repo()

Uses tmp_path fixture exclusively — no real repo paths.
All 4 tests match the acceptance criteria in tickets/open/STEP-10-C.yaml.
"""
import pytest
from pathlib import Path
from agent.context_budget import ContextBudget


# ─────────────────────────────────────────────────────────────────────────────
# 1. test_graphify_populates_cache
# ─────────────────────────────────────────────────────────────────────────────

def test_graphify_populates_cache(tmp_path):
    """graphify_repo scans 3 files, returns files_scanned==3, populates _file_hashes."""
    (tmp_path / "test.py").write_text("x = 1\n")
    (tmp_path / "readme.md").write_text("# Test\n")
    (tmp_path / "config.yaml").write_text("key: value\n")

    budget = ContextBudget(cache_path=str(tmp_path / "ctx-cache.json"))
    result = budget.graphify_repo(repo_path=str(tmp_path))

    # Return structure
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result

    # files_scanned key present and correct
    assert result["metadata"]["files_scanned"] == 3

    # Cache populated with 3 resolved paths
    assert len(budget._file_hashes) == 3


# ─────────────────────────────────────────────────────────────────────────────
# 2. test_graphify_cached_on_rescan
# ─────────────────────────────────────────────────────────────────────────────

def test_graphify_cached_on_rescan(tmp_path):
    """After graphify_repo() twice with no changes, should_read() returns (False, 'cached')."""
    md_file = tmp_path / "readme.md"
    md_file.write_text("# Test\n")

    budget = ContextBudget(cache_path=str(tmp_path / "ctx-cache.json"))
    budget.graphify_repo(repo_path=str(tmp_path))
    budget.graphify_repo(repo_path=str(tmp_path))  # second scan — same content

    flag, reason = budget.should_read(str(md_file))
    assert flag is False
    assert reason == "cached"


# ─────────────────────────────────────────────────────────────────────────────
# 3. test_graphify_changed_on_modify
# ─────────────────────────────────────────────────────────────────────────────

def test_graphify_changed_on_modify(tmp_path):
    """After graphify_repo(), modifying a file makes should_read() return 'changed'."""
    py_file = tmp_path / "test.py"
    py_file.write_text("x = 1\n")

    budget = ContextBudget(cache_path=str(tmp_path / "ctx-cache.json"))
    budget.graphify_repo(repo_path=str(tmp_path))

    # Mutate the file — hash changes, but session_reads still has the old resolved path
    py_file.write_text("x = 1\ny = 2\n")

    flag, reason = budget.should_read(str(py_file))
    # File is in _file_hashes (seen before) but hash differs → "changed"
    assert reason == "changed"


# ─────────────────────────────────────────────────────────────────────────────
# 4. test_graphify_zone_assignment
# ─────────────────────────────────────────────────────────────────────────────

def test_graphify_zone_assignment(tmp_path):
    """graphify_repo assigns zones: AI-FIRST→docs_cache, tickets→ticket_context, logs→scratch_pad."""
    (tmp_path / "AI-FIRST").mkdir()
    (tmp_path / "AI-FIRST" / "step08.md").write_text("# Step 08\n")

    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "ticket.yaml").write_text("ticket_id: T1\n")

    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "log.md").write_text("## Log\n")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main(): pass\n")

    budget = ContextBudget(cache_path=str(tmp_path / "ctx-cache.json"))
    result = budget.graphify_repo(repo_path=str(tmp_path))

    zs = result["metadata"]["zone_summary"]

    # tickets/ → ticket_context
    assert zs["ticket_context"] == 1, f"Expected 1 ticket_context, got {zs}"
    # logs/ → scratch_pad
    assert zs["scratch_pad"] == 1, f"Expected 1 scratch_pad, got {zs}"
    # AI-FIRST/ + src/ → docs_cache (≥ 2)
    assert zs["docs_cache"] >= 2, f"Expected >=2 docs_cache, got {zs}"
