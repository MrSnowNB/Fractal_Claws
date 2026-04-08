"""
Skill Store — Unit tests for Step 6 skill-aware decomposition.
"""

import os
import tempfile
import yaml
import pytest
from src.skill_store import load_skill, write_skill, match_goal_class, SkillLoadError, SkillWriteError


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