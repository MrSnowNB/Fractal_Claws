"""tests/test_harness_artifacts.py

Post-run assertion suite for the harness integration test (TASK-008 through TASK-011).
Run AFTER python agent/runner.py --no-prewarm completes all tickets.

Usage:
    pytest -q tests/test_harness_artifacts.py

All tests are read-only. No side effects. Safe to re-run.
"""

import json
import os
import pytest


ARTIFACTS = [
    "output/word_freq.py",
    "output/report.md",
    "output/audit.json",
    "output/harness_result.json",
]

ATTEMPT_LOGS = [
    "logs/TASK-008-attempts.jsonl",
    "logs/TASK-009-attempts.jsonl",
    "logs/TASK-010-attempts.jsonl",
    "logs/TASK-011-attempts.jsonl",
]


@pytest.mark.parametrize("path", ARTIFACTS)
def test_artifact_exists(path):
    assert os.path.exists(path), f"Missing artifact: {path}"


@pytest.mark.parametrize("path", ARTIFACTS)
def test_artifact_nonempty(path):
    if not os.path.exists(path):
        pytest.skip(f"artifact missing: {path}")
    assert os.path.getsize(path) > 0, f"Empty artifact: {path}"


def test_word_freq_contains_the():
    path = "output/word_freq.py"
    if not os.path.exists(path):
        pytest.skip("word_freq.py missing")
    content = open(path).read()
    assert "the" in content.lower(), "word_freq.py must reference 'the'"


def test_report_contains_top_words_section():
    path = "output/report.md"
    if not os.path.exists(path):
        pytest.skip("report.md missing")
    content = open(path).read()
    assert "## Top Words" in content, "report.md must contain '## Top Words' section"


def test_audit_json_schema():
    path = "output/audit.json"
    if not os.path.exists(path):
        pytest.skip("audit.json missing")
    with open(path) as f:
        data = json.load(f)
    assert data.get("test_run") == "harness-integration-v1"
    assert data.get("report_contains_top_words") is True
    assert isinstance(data.get("report_char_count"), int)
    assert isinstance(data.get("artifacts_produced"), list)
    assert "ts" in data


def test_harness_result_passed():
    path = "output/harness_result.json"
    if not os.path.exists(path):
        pytest.skip("harness_result.json missing")
    with open(path) as f:
        data = json.load(f)
    assert data.get("passed") is True, (
        f"Harness result not passed. failed_checks: {data.get('failed_checks')}"
    )


@pytest.mark.parametrize("path", ATTEMPT_LOGS)
def test_attempt_log_exists(path):
    assert os.path.exists(path), f"Missing attempt log: {path}"


@pytest.mark.parametrize("path", ATTEMPT_LOGS)
def test_attempt_log_valid_jsonl(path):
    if not os.path.exists(path):
        pytest.skip(f"log missing: {path}")
    lines = open(path).read().strip().splitlines()
    assert len(lines) >= 1, f"Empty attempt log: {path}"
    for i, line in enumerate(lines):
        record = json.loads(line)  # raises on invalid JSON
        assert "outcome" in record, f"{path} line {i+1} missing 'outcome' field"
        assert "ticket_id" in record, f"{path} line {i+1} missing 'ticket_id' field"
        assert "tokens" in record, f"{path} line {i+1} missing 'tokens' field"
        assert record["outcome"] in ("pass", "fail", "error"), (
            f"{path} line {i+1} invalid outcome: {record['outcome']}"
        )


@pytest.mark.parametrize("path", ATTEMPT_LOGS)
def test_attempt_log_has_pass_outcome(path):
    """At least one attempt per ticket must have outcome=pass (ticket closed)."""
    if not os.path.exists(path):
        pytest.skip(f"log missing: {path}")
    lines = open(path).read().strip().splitlines()
    outcomes = [json.loads(l)["outcome"] for l in lines]
    assert "pass" in outcomes, (
        f"{path}: no passing attempt found. outcomes={outcomes}"
    )
