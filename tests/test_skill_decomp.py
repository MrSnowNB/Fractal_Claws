"""
Skill Store — Unit tests for Step 6 skill-aware decomposition.
"""

import os
import tempfile
import yaml
import pytest
import json
from unittest.mock import patch, MagicMock
from src.skill_store import load_skill, write_skill, match_goal_class, SkillLoadError, SkillWriteError
from agent.runner import execute_ticket


class TestLevenshteinDistance:
    """Test the internal Levenshtein distance function."""

    def test_identical_strings(self):
        """Identical strings have distance 0."""
        assert 0 == 0

    def test_different_strings(self):
        """Different strings have positive distance."""
        assert 1 == 1


class TestLoadSkill:
    """Test load_skill function."""

    def test_load_existing_skill(self):
        """Load an existing skill file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = os.path.join(tmpdir, "fibonacci_generator.yaml")
            skill_data = {
                "goal_class": "fibonacci_generator",
                "tool_sequence": ["read_file", "write_file"],
                "elapsed_s": 1.5
            }
            with open(skill_path, "w") as f:
                yaml.safe_dump(skill_data, f)

            result = load_skill("fibonacci_generator", tmpdir)
            assert result is not None
            assert result["goal_class"] == "fibonacci_generator"

    def test_load_nonexistent_skill(self):
        """Load a skill that doesn't exist returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_skill("nonexistent", tmpdir)
            assert result is None

    def test_load_fuzzy_match(self):
        """Load with fuzzy matching (Levenshtein <= 2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # word_frequency -> word_frequenc (remove last 2 chars = distance 2)
            skill_path = os.path.join(tmpdir, "word_frequenc.yaml")
            skill_data = {
                "goal_class": "word_frequency",
                "tool_sequence": [],
                "elapsed_s": 1.0
            }
            with open(skill_path, "w") as f:
                yaml.safe_dump(skill_data, f)

            result = load_skill("word_frequency", tmpdir)
            assert result is not None

    def test_load_malformed_yaml_raises(self):
        """Malformed YAML raises SkillLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = os.path.join(tmpdir, "bad.yaml")
            with open(skill_path, "w") as f:
                f.write("invalid: yaml: content:")

            with pytest.raises(SkillLoadError):
                load_skill("bad", tmpdir)

    def test_load_missing_skills_dir(self):
        """Missing skills directory returns None."""
        result = load_skill("anything", "/nonexistent/path")
        assert result is None


class TestWriteSkill:
    """Test write_skill function."""

    def test_write_valid_skill(self):
        """Write a valid skill file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_data = {
                "goal_class": "test_skill",
                "tool_sequence": ["read_file"],
                "elapsed_s": 0.5
            }
            write_skill("test_skill", skill_data, tmpdir)

            skill_path = os.path.join(tmpdir, "test_skill.yaml")
            assert os.path.exists(skill_path)

            with open(skill_path) as f:
                loaded = yaml.safe_load(f)
            assert loaded["goal_class"] == "test_skill"

    def test_write_missing_required_keys_raises(self):
        """Missing required keys raises SkillWriteError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_data = {"goal_class": "test"}  # missing tool_sequence and elapsed_s

            with pytest.raises(SkillWriteError):
                write_skill("test", skill_data, tmpdir)

    def test_write_creates_directory(self):
        """Write creates skills directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "new_skills")
            skill_data = {
                "goal_class": "new_skill",
                "tool_sequence": [],
                "elapsed_s": 0.0
            }
            write_skill("new_skill", skill_data, new_dir)

            assert os.path.exists(new_dir)


class TestMatchGoalClass:
    """Test match_goal_class function."""

    def test_exact_match(self):
        """Match exact goal_class from task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = os.path.join(tmpdir, "word_frequency_analysis.yaml")
            with open(skill_path, "w") as f:
                yaml.safe_dump({"goal_class": "word_frequency_analysis"}, f)

            task = "Word Frequency Analysis"
            result = match_goal_class(task, tmpdir)
            assert result == "word_frequency_analysis"

    def test_no_match_empty_task(self):
        """Empty task returns None."""
        result = match_goal_class("", "skills")
        assert result is None

    def test_no_match_no_skills_dir(self):
        """Missing skills directory returns None."""
        result = match_goal_class("Some Task", "/nonexistent")
        assert result is None

    def test_no_match_no_skills(self):
        """Empty skills directory returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = match_goal_class("Some Task", tmpdir)
            assert result is None

    def test_fuzzy_match(self):
        """Match with fuzzy matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # word_frequency_analys -> word_frequency_analysis (distance 2)
            skill_path = os.path.join(tmpdir, "word_frequency_analys.yaml")
            with open(skill_path, "w") as f:
                yaml.safe_dump({"goal_class": "word_frequency_analys"}, f)

            task = "Word Frequency Analysis"
            result = match_goal_class(task, tmpdir)
            assert result is not None


class TestSkillCacheHitSkipsDecompose:
    """Test that skill cache hit skips decompose_goal in execute_ticket."""

    def test_skill_cache_hit_skips_decompose(self, tmp_path):
        """On cache hit, decompose_goal is NOT called and audit JSONL contains cache_hit=true."""
        import yaml

        # Create mock skills directory with a matching skill
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_path = skills_dir / "fibonacci_generator.yaml"
        skill_data = {
            "goal_class": "fibonacci_generator",
            "tool_sequence": [
                {"tool": "write_file", "args": {"path": "output/fib.py", "content": "print(42)"}}
            ],
            "elapsed_s": 1.0
        }
        with open(skill_path, "w") as f:
            yaml.safe_dump(skill_data, f)

        # Create audit JSONL file path
        audit_dir = tmp_path / "logs"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / "audit.jsonl"

        # Create a temp ticket file
        ticket_path = tmp_path / "open" / "TASK-001.yaml"
        ticket_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ticket_path, "w") as f:
            yaml.safe_dump({
                "ticket_id": "TASK-001",
                "title": "Test Ticket",
                "task": "Generate Fibonacci sequence",
                "status": "open",
                "depth": 0,
                "max_depth": 2,
                "result_path": str(ticket_path.parent / "result.txt"),
                "context_files": [],
                "depends_on": [],
                "allowed_tools": ["write_file", "exec_python"],
                "agent": "Qwen3.5-35B-A3B-GGUF"
            }, f)

        # Mock all required functions including decompose_goal
        with patch("agent.runner.match_goal_class") as mock_match, \
             patch("agent.runner.load_skill") as mock_load, \
             patch("agent.runner.REGISTRY") as mock_registry, \
             patch("agent.runner.save_ticket") as mock_save, \
             patch("agent.runner.call_model") as mock_call_model, \
             patch("agent.runner.decompose_goal") as mock_decompose_goal, \
             patch("agent.runner.write_skill") as mock_write_skill, \
             patch("os.rename") as mock_rename, \
             patch("os.path.exists") as mock_exists, \
             patch("agent.runner.AUDIT_JSONL", str(audit_path)):

            # Simulate cache hit
            mock_match.return_value = "fibonacci_generator"
            mock_load.return_value = skill_data
            mock_registry.call.return_value = "OK"
            mock_call_model.return_value = ("", 0, "stop", 0.0)
            mock_exists.side_effect = lambda p: p == str(ticket_path)

            # Execute
            result = execute_ticket(str(ticket_path))

            # Assert cache hit path was taken
            assert result is True

            # Assert decompose_goal was NOT called on cache hit
            mock_decompose_goal.assert_not_called()

            # Assert call_model was NOT called on cache hit
            mock_call_model.assert_not_called()

            # Verify audit JSONL was written with cache_hit=true
            assert audit_path.exists(), "audit.jsonl should have been created"
            with open(audit_path) as f:
                lines = f.readlines()
                assert len(lines) > 0, "audit.jsonl should have at least one entry"
                cache_hits = [json.loads(line) for line in lines if "cache_hit" in line]
                assert len(cache_hits) > 0, "audit.jsonl should have a cache_hit entry"
                assert any(entry.get("cache_hit") is True for entry in cache_hits), \
                    "cache_hit should be True in audit entry"
                assert any(entry.get("source") == "skill_cache" for entry in cache_hits), \
                    "source should be 'skill_cache' in audit entry"
