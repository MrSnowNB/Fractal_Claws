---
title: TROUBLESHOOTING Guide
version: "0.1.0"
last_updated: "2026-04-05"
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
## TS-20260405-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260405-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260405-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260405-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260405-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260406-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260406-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
## TS-20260406-TASK-005

- **Context**: Ticket TASK-005 in phase unknown
- **Symptom**: Test failure
- **Error Snippet**: `Test failure...`
- **Probable Cause**: [To be determined]
- **Quick Fix**: [Not applicable - halt state]
- **Permanent Fix**: [To be determined after human review]
- **Prevention**: [To be determined]
- **Status**: Halted - awaiting human instruction
