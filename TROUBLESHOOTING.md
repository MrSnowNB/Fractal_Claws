---
title: TROUBLESHOOTING Guide
version: "0.1.0"
last_updated: "2026-04-06"
---

# TROUBLESHOOTING.md — Failure Log

## Seeded Entries

### TS-001: MT-01 Gate Failure — Model Selection
**Context:** MT-01 test execution fails at any test case.  
**Symptom:** Test case does not pass 5/5 consecutive runs.  
**Error Snippet:** `test_case: TC-XX, passes: 0/5, failures: 5/5`  
**Probable Cause:** Model slot not properly configured or model does not meet pass threshold (28/30).  
**Quick Fix:** Check settings.yaml model configuration and Lemonade endpoint connectivity.  
**Permanent Fix:** Run MT-01 protocol fully; if failures persist, update model slot assignment.  
**Prevention:** Always run MT-01 before any phase transition to Build.  
**Recurrence:** _none yet_

---

### TS-002: Context Window Exhaustion
**Context:** Orchestrator runs out of context during task.  
**Symptom:** Agent halts with "context budget exceeded" warning.  
**Error Snippet:** `context utilization > 80%`  
**Probable Cause:** Task scope too broad or checkpoint not written at 60%.  
**Quick Fix:** Write CHECKPOINT.md and truncate history.  
**Permanent Fix:** Break task into atomic subtasks per .clinerules 04-qwen-coder.md.  
**Prevention:** Monitor context utilization; write CHECKPOINT.md at 60%.

---

### TS-003: Ticket Escalation Loop
**Context:** Ticket remains in escalated state.  
**Symptom:** Ticket stuck at status: escalated, attempts > 0.  
**Error Snippet:** `decrement: 0, status: escalated, no parent response`  
**Probable Cause:** Parent ticket closed or not processing child results.  
**Quick Fix:** Check parent ticket status; reassign to available depth slot.  
**Permanent Fix:** Implement ticket callback mechanism.  
**Prevention:** Validate ticket hierarchy before execution.

---

### TS-004: Validation Gate Non-Green
**Context:** Unit, lint, type, or spec_drift gate fails.  
**Symptom:** Gate command returns non-zero exit code.  
**Error Snippet:** `pytest -q: 1 failed, 1 error` or `ruff: 3 issues found`  
**Probable Cause:** Code changes introduced regressions or style violations.  
**Quick Fix:** Fix reported issues; re-run gate commands.  
**Permanent Fix:** Implement pre-commit hook to run all gates.  
**Prevention:** Run gates after every change; require consecutive passes.

---

## Log Format

Append new entries using this template:

```yaml
TS-XXX:
  timestamp: "YYYY-MM-DD HH:MM:SS"
  context: <brief description>
  symptom: <observed failure>
  error_snippet: <relevant output>
  probable_cause: <root cause>
  quick_fix: <immediate remediation>
  permanent_fix: <long-term fix>
  prevention: <how to prevent recurrence>
  recurrence: <true/false>
```

---

### TS-20260406-001: Runner 4B Model Empty Choices

**Context**: Runner attempts to spawn Qwen3.5-4B-GGUF model via Lemonade endpoint.  
**Symptom**: Model consistently returns `empty choices` across all retry attempts.  
**Error Snippet**: `[model] attempt N: empty choices — retry in 4s` (4 consecutive failures)  
**Probable Cause**: Lemonade endpoint returning no response choices or model not loaded properly.  
**Quick Fix**: Verify Lemonade endpoint `http://localhost:8000/api/v1` is serving Qwen3.5-4B-GGUF model; check Lemonade logs.  
**Permanent Fix**: Re-load model or restart Lemonade service if endpoint is unresponsive.  
**Prevention**: Add pre-flight health check to runner.py before attempting model calls.  
**Recurrence**: false

---

### TS-20260406-002: Ticket TASK-014 Decomposition Failure

**Context**: Ticket TASK-014 failed during goal decomposition phase.  
**Symptom**: Decomposition produced no tickets — abort.  
**Error Snippet**: `[runner] decompose failed: model call failed after 4 attempts`  
**Probable Cause**: Model endpoint `http://localhost:8000/api/v1` returned empty choices.  
**Quick Fix**: Verify Lemonade service is running and model Qwen3.5-4B-GGUF is loaded.  
**Permanent Fix**: Restart Lemonade service and reload model configuration.  
**Prevention**: Implement endpoint health check before decompose phase.  
**Recurrence**: true (see TS-20260406-001)