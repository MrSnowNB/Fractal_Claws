---
title: ISSUE.md
version: "2026-04-07-v3"
last_updated: "2026-04-07"
---

# ISSUE.md — Issue Log

> **All issues related to Qwen3.5-4B-GGUF are CLOSED and ARCHIVED.**
> The 4B model is DEPRECATED — deferred to future integration.
> There are NO open action items related to 4B. Do not attempt to fix or load it.

---

## Open Issues

### ISS-20260407-003: runner.py max_retries exceeded (YOLO kill at 3)

- **Status**: OPEN
- **Title**: runner.py terminated after max_retries (3) exceeded during TASK-001
- **Date**: 2026-04-07
- **Context**: Task runner.py terminated with "max_retries exceeded" after 3 attempts during TASK-001 execution
- **Root Cause**: settings.yaml had max_retries=3 but policy requires stop at 2 (YOLO kills at 3)
- **Resolution**: settings.yaml max_retries reduced to 2; pre_flight.py now validates max_retries ≤ 2
- **Human action required**: None — policy fix implemented, REPLICATION-NOTES.md updated

---

### ISS-20260407-002: 4B Model (duplicate entry)
### ISS-20260407-002: 4B Model (duplicate entry)

---

## Closed / Archived

### ISS-20260406-001: Runner 4B Model Empty Choices

- **Status**: CLOSED ✅ — ARCHIVED
- **Title**: Runner could not spawn Qwen3.5-4B-GGUF
- **Resolution**: Switched to Qwen3.5-35B-A3B-GGUF. Full fib.txt run completed 2026-04-07 with 8 tickets PASS.
- **4B role**: DEPRECATED — deferred to future integration phase. Not a blocker.
- **Human action required**: None.

---

### ISS-20260407-001: 4B Model Unavailable - Consistent Empty Choices

- **Status**: CLOSED ✅ — ARCHIVED
- **Title**: Qwen3.5-4B-GGUF cannot produce valid YAML output
- **Resolution**: 4B formally deprecated. Active harness uses Coder-Next (parent) + A3B (child).
- **Human action required**: None.

---

### ISS-20260407-002: 4B Model (duplicate entry)

- **Status**: CLOSED ✅ — ARCHIVED (duplicate of ISS-20260407-001)
- **Human action required**: None.

---

### ISS-20260410-001: STEP-11-B Validation Gate Test Fixture Issues

- **Status**: BLOCKED ❌
- **Title**: Test fixture misconfiguration blocks STEP-11-B validation
- **Date**: 2026-04-10
- **Context**: STEP-11-B task (hook Law §1 in execute_ticket()) ran pytest - 8 failures in test_luffy_law.py due to test fixture issues, not code change
- **Root Cause**: Test fixtures use temp_log_dir but implementation checks logs/ directory directly
- **Symptoms**:
  - validate_scratch tests: check logs/scratch-*.jsonl but test passes temp_log_dir
  - assert_scratch_written tests: look in logs/ but test creates files in temp_log_dir
  - test_drain_emits_scratchpad_read_on_first_read: CTX_BUDGET not imported
  - test_ticket_closes_only_with_scratch_events: same scratch path issue
- **Quick Fix**: Fix test fixtures to write/read scratch files in logs/ directory, or update implementation to accept log_dir parameter
- **Permanent Fix**: Audit test fixtures in conftest.py; ensure temp_log_dir fixture writes to correct path or update implementation to accept log_dir parameter
- **Human action required**: Review and approve fix for test fixture path mismatch before STEP-11-B can proceed
- **Related**: TROUBLESHOOTING.md TS-20260410-001

---

### ISS-20260406-TASK-005: Failure in ticket TASK-005

- **Status**: CLOSED ✅ — ARCHIVED
- **Resolution**: Superseded by full POC run 2026-04-07. All tickets PASS.
- **Human action required**: None.
