#!/usr/bin/env python3
"""tests/test_trajectory.py — 12 trajectory extractor tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml
from trajectory_extractor import (
    extract_trajectory,
    goal_class,
    write_skill,
    run_extraction,
)


def test_extract_trajectory_pass(tmp_path):
    """Write a JSONL with one record: {"outcome": "pass", "ticket_id": "T001", "elapsed_s": 1.5}.
    Call extract_trajectory("T001", log_dir=str(log_dir)).
    Assert result["outcome"] == "pass".
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    record = {"outcome": "pass", "ticket_id": "T001", "elapsed_s": 1.5}
    jsonl_path = log_dir / "T001-attempts.jsonl"
    jsonl_path.write_text('{"outcome": "pass", "ticket_id": "T001", "elapsed_s": 1.5}\n')

    result = extract_trajectory("T001", log_dir=str(log_dir))
    assert result is not None
    assert result["outcome"] == "pass"


def test_extract_trajectory_no_file(tmp_path):
    """Call extract_trajectory("NONEXISTENT", log_dir=str(log_dir)) where log_dir is empty.
    Assert result is None.
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    result = extract_trajectory("NONEXISTENT", log_dir=str(log_dir))
    assert result is None


def test_extract_trajectory_no_pass(tmp_path):
    """Write JSONL with only fail records.
    Assert extract_trajectory returns None.
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    jsonl_path = log_dir / "T002-attempts.jsonl"
    jsonl_path.write_text(
        '{"outcome": "fail", "ticket_id": "T002"}\n'
        '{"outcome": "fail", "ticket_id": "T002"}\n'
    )

    result = extract_trajectory("T002", log_dir=str(log_dir))
    assert result is None


def test_extract_trajectory_first_pass(tmp_path):
    """Write JSONL with: fail, pass (elapsed_s=2.0), pass (elapsed_s=1.0).
    Assert result["elapsed_s"] == 2.0 (FIRST pass wins, not best).
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    jsonl_path = log_dir / "T003-attempts.jsonl"
    jsonl_path.write_text(
        '{"outcome": "fail", "ticket_id": "T003"}\n'
        '{"outcome": "pass", "ticket_id": "T003", "elapsed_s": 2.0}\n'
        '{"outcome": "pass", "ticket_id": "T003", "elapsed_s": 1.0}\n'
    )

    result = extract_trajectory("T003", log_dir=str(log_dir))
    assert result is not None
    assert result["elapsed_s"] == 2.0


def test_extract_trajectory_skips_malformed(tmp_path):
    """Write JSONL: "not json\n" + valid pass record.
    Assert result["outcome"] == "pass" (malformed line skipped).
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    jsonl_path = log_dir / "T004-attempts.jsonl"
    jsonl_path.write_text(
        'not json\n'
        '{"outcome": "pass", "ticket_id": "T004"}\n'
    )

    result = extract_trajectory("T004", log_dir=str(log_dir))
    assert result is not None
    assert result["outcome"] == "pass"


def test_goal_class_from_tags():
    """ticket = {"tags": ["write", "python", "test", "extra"]}
    Assert goal_class(ticket) == "write-python-test".
    """
    ticket = {"tags": ["write", "python", "test", "extra"]}
    result = goal_class(ticket)
    assert result == "write-python-test"


def test_goal_class_from_title():
    """ticket = {"title": "Generate Fibonacci", "tags": []}
    Assert goal_class(ticket) == "generate-fibonacci".
    """
    ticket = {"title": "Generate Fibonacci", "tags": []}
    result = goal_class(ticket)
    assert result == "generate-fibonacci"


def test_goal_class_from_tags_with_spaces():
    """ticket = {"tags": ["Write Python", "Test Code"]}
    Assert goal_class(ticket) == "write-python-test-code".
    """
    ticket = {"tags": ["Write Python", "Test Code"]}
    result = goal_class(ticket)
    assert result == "write-python-test-code"


def test_goal_class_max_length():
    """ticket = {"title": "A" * 200, "tags": []}
    Assert len(goal_class(ticket)) <= 48.
    """
    ticket = {"title": "A" * 200, "tags": []}
    result = goal_class(ticket)
    assert len(result) <= 48


def test_write_skill_creates_file(tmp_path):
    """Call write_skill("test-skill", {"elapsed_s": 1.0, "tool_calls": 2, "tokens": 100,
    "tok_s": 100.0, "finish": "stop", "attempt": 1, "ts": "2026-04-07T00:00:00"},
    {"ticket_id": "T001", "tags": [], "produces": [], "consumes": []}, skills_dir=str(skills_dir)).
    Assert YAML file exists and contains goal_class == "test-skill".
    """
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    trajectory = {
        "elapsed_s": 1.0,
        "tool_calls": 2,
        "tokens": 100,
        "tok_s": 100.0,
        "finish": "stop",
        "attempt": 1,
        "ts": "2026-04-07T00:00:00",
    }
    ticket = {
        "ticket_id": "T001",
        "tags": [],
        "produces": [],
        "consumes": [],
    }

    result_path = write_skill("test-skill", trajectory, ticket, skills_dir=str(skills_dir))
    assert result_path == str(skills_dir / "test-skill.yaml")

    skill_yaml = skills_dir / "test-skill.yaml"
    assert skill_yaml.exists()

    with open(skill_yaml, "r", encoding="utf-8") as f:
        skill = yaml.safe_load(f)
    assert skill["goal_class"] == "test-skill"


def test_write_skill_keeps_best(tmp_path):
    """Write an existing skill YAML with elapsed_s: 0.5.
    Call write_skill with elapsed_s=1.5.
    Assert file still contains elapsed_s: 0.5 (existing is better).
    """
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create existing skill with elapsed_s: 0.5
    existing_skill = {
        "goal_class": "test-skill",
        "elapsed_s": 0.5,
    }
    skill_yaml = skills_dir / "test-skill.yaml"
    with open(skill_yaml, "w", encoding="utf-8") as f:
        yaml.dump(existing_skill, f)

    # New trajectory with elapsed_s=1.5 (worse)
    new_trajectory = {
        "elapsed_s": 1.5,
        "tool_calls": 2,
        "tokens": 100,
        "tok_s": 100.0,
        "finish": "stop",
        "attempt": 1,
        "ts": "2026-04-07T00:00:00",
    }
    ticket = {
        "ticket_id": "T001",
        "tags": [],
        "produces": [],
        "consumes": [],
    }

    result_path = write_skill("test-skill", new_trajectory, ticket, skills_dir=str(skills_dir))
    assert result_path == str(skills_dir / "test-skill.yaml")

    with open(skill_yaml, "r", encoding="utf-8") as f:
        skill = yaml.safe_load(f)
    assert skill["elapsed_s"] == 0.5


def test_write_skill_replaces_worse(tmp_path):
    """Write existing skill YAML with elapsed_s: 5.0.
    Call write_skill with elapsed_s=1.0.
    Assert file now contains elapsed_s: 1.0.
    """
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create existing skill with elapsed_s: 5.0
    existing_skill = {
        "goal_class": "test-skill",
        "elapsed_s": 5.0,
    }
    skill_yaml = skills_dir / "test-skill.yaml"
    with open(skill_yaml, "w", encoding="utf-8") as f:
        yaml.dump(existing_skill, f)

    # New trajectory with elapsed_s=1.0 (better)
    new_trajectory = {
        "elapsed_s": 1.0,
        "tool_calls": 2,
        "tokens": 100,
        "tok_s": 100.0,
        "finish": "stop",
        "attempt": 1,
        "ts": "2026-04-07T00:00:00",
    }
    ticket = {
        "ticket_id": "T001",
        "tags": [],
        "produces": [],
        "consumes": [],
    }

    result_path = write_skill("test-skill", new_trajectory, ticket, skills_dir=str(skills_dir))
    assert result_path == str(skills_dir / "test-skill.yaml")

    with open(skill_yaml, "r", encoding="utf-8") as f:
        skill = yaml.safe_load(f)
    assert skill["elapsed_s"] == 1.0


def test_run_extraction_integration(tmp_path):
    """Create tmp_closed_dir with one ticket YAML:
    ticket_id: INT-001, tags: [integration, test], produces: [], consumes: []
    Create matching JSONL at tmp_log_dir/INT-001-attempts.jsonl:
    {"outcome": "pass", "ticket_id": "INT-001", "elapsed_s": 2.0,
     "tool_calls": 3, "tokens": 200, "tok_s": 100.0, "finish": "stop", "attempt": 1,
     "ts": "2026-04-07T00:00:00"}
    Call run_extraction(closed_dir=str(tmp_closed_dir), log_dir=str(tmp_log_dir)).
    Assert skills/<goal_class>.yaml exists and goal_class == "integration-test".
    """
    closed_dir = tmp_path / "tickets" / "closed"
    closed_dir.mkdir(parents=True)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create ticket YAML
    ticket_yaml = closed_dir / "INT-001.yaml"
    ticket_content = {
        "ticket_id": "INT-001",
        "tags": ["integration", "test"],
        "produces": [],
        "consumes": [],
    }
    with open(ticket_yaml, "w", encoding="utf-8") as f:
        yaml.dump(ticket_content, f)

    # Create JSONL (single-line JSON per line for valid JSONL)
    jsonl_path = log_dir / "INT-001-attempts.jsonl"
    jsonl_path.write_text(
        '{"outcome": "pass", "ticket_id": "INT-001", "elapsed_s": 2.0, "tool_calls": 3, "tokens": 200, "tok_s": 100.0, "finish": "stop", "attempt": 1, "ts": "2026-04-07T00:00:00"}\n'
    )

    paths = run_extraction(closed_dir=str(closed_dir), log_dir=str(log_dir), skills_dir=str(skills_dir))
    assert len(paths) == 1
    assert "integration-test" in paths[0]

    skill_yaml = skills_dir / "integration-test.yaml"
    assert skill_yaml.exists()

    with open(skill_yaml, "r", encoding="utf-8") as f:
        skill = yaml.safe_load(f)
    assert skill["goal_class"] == "integration-test"
