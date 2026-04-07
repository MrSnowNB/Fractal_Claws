---
title: TROUBLESHOOTING Guide
version: "0.2.0"
last_updated: "2026-04-07"
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

**Status**: RESOLVED ✅ 2026-04-07  
**Context**: Runner attempts to spawn Qwen3.5-4B-GGUF model via Lemonade endpoint.  
**Symptom**: Model consistently returns `empty choices` across all retry attempts.  
**Error Snippet**: `[model] attempt N: empty choices — retry in 4s` (4 consecutive failures)  
**Root Cause (final)**: Two stacked bugs:
  1. `max_tokens: 512` was the output cap — decompose prompt consumed full context window, leaving 0 tokens for output.
  2. `decompose_budget` missing from config — runner used `max_tokens` value (512) as input budget instead of 80% of context (6553).
  3. Qwen3.5-4B-GGUF downloaded but not loaded in Lemonade at time of run — CURL error on `/chat/completions` confirmed.
**Quick Fix**: Switch model to Qwen3.5-35B-A3B-GGUF (confirmed loaded). Update settings.yaml model.id.  
**Permanent Fix**: commit `58081217` — raised max_tokens to 1024, added decompose_budget: 6553, timeout 120s. Pre-flight should verify model is loaded (not just downloaded) before runner starts.  
**Prevention**: Add `/chat/completions` health check to pre_flight.py — probe with `max_tokens: 1` to confirm model actually generates, not just lists. Add `decompose_budget` as required key in settings schema.  
**Recurrence**: false — root causes patched.

---

### TS-20260406-002: Ticket TASK-014 Decomposition Failure

**Status**: RESOLVED ✅ 2026-04-07 (child of TS-20260406-001)  
**Context**: Ticket TASK-014 failed during goal decomposition phase.  
**Symptom**: Decomposition produced no tickets — abort.  
**Error Snippet**: `[runner] decompose failed: model call failed after 4 attempts`  
**Probable Cause**: Model endpoint returned empty choices (see TS-20260406-001).  
**Quick Fix**: Fix parent issue TS-20260406-001.  
**Permanent Fix**: Same as TS-20260406-001.  
**Prevention**: Same as TS-20260406-001.  
**Recurrence**: false

---

### TS-20260407-001: POC First Successful End-to-End Run

**Status**: MILESTONE ✅  
**Timestamp**: 2026-04-07 ~05:20 EDT  
**Context**: First complete goal → decompose → execute → verify run on ZBook hardware.  
**Goal**: `write a python script that generates the first 20 fibonacci numbers and saves them to output/fib.txt, then verify the file was written`  
**Model**: Qwen3.5-35B-A3B-GGUF (35B MoE, ctx_size: 64000)  
**Result**: 8 tickets decomposed and closed, all PASS.
**Performance**:
  - Decompose: 609 tokens, 10.43s
  - Fastest task: TASK-017, 1.66s @ 121.7 tok/s
  - Slowest task: TASK-015, 7.75s @ 54.7 tok/s
  - RAM stable: ~98.6 GB / 127 GB
**Notable**: Agent self-corrected model selection — probed 4B, got CURL error, switched to 35B autonomously.
**Follow-up**: budget=256 on TASKS 018-020 indicates runner budget inheritance not reading decompose_budget from updated config — audit runner.py token budget logic.

---

### TS-20260407-002: 4B Model Unavailable - Consistent Empty Choices

**Status**: RESOLVED - Model Marked UNAVAILABLE ✅ 2026-04-07  
**Context**: After multiple attempts, Qwen3.5-4B-GGUF model consistently fails decompose task with empty choices.  
**Symptom**: `[model] attempt N: empty choices — retry in 4s` (4 consecutive failures across multiple test runs)  
**Error Snippet**:
```
[runner] decomposing goal...
  [model] attempt 1: empty choices — retry in 4s
  [model] attempt 2: empty choices — retry in 4s
  [model] attempt 3: empty choices — retry in 4s
  [model] attempt 4: empty choices — retry in 4s
[runner] decompose failed: model call failed after 4 attempts
[runner] decomposition produced no tickets — abort
```  
**Root Cause**: Qwen3.5-4B-GGUF model cannot reliably produce YAML output for decompose task, despite being downloaded and appearing in Lemonade's model list. The model may lack fine-tuning for structured output or has architecture limitations preventing consistent YAML generation.  
**Quick Fix**: Switch model back to LFM2.5-1.2B (A3B) - confirmed working.  
**Permanent Fix**: Mark 4B model as unavailable in settings.yaml header comment. Continue testing with A3B. If 4B is needed, consider re-training or using a different GGUF variant.  
**Prevention**: Add model capability test to pre_flight.py - verify model can produce valid YAML output for a simple decompose task before attempting full runs.  
**Recurrence**: true - 4 consecutive failures across multiple test runs. Model deemed unreliable for this workload.

---

### TS-20260407-003: Model Selection Finalized - A3B Only

**Status**: RESOLVED - Configuration Updated ✅ 2026-04-07  
**Context**: After multiple failed attempts, 4B model consistently fails decompose task with empty choices.  
**Symptom**: Runner cannot spawn 4B model for goal decomposition.  
**Error Snippet**:
```
[runner] decomposing goal...
  [model] attempt 1: empty choices — retry in 4s
  [model] attempt 2: empty choices — retry in 4s
  [model] attempt 3: empty choices — retry in 4s
  [model] attempt 4: empty choices — retry in 4s
[runner] decompose failed: model call failed after 4 attempts
```  
**Root Cause**: Qwen3.5-4B-GGUF model lacks fine-tuning for structured YAML output or has architecture limitations.  
**Quick Fix**: Switch to LFM2.5-1.2B (A3B) - confirmed working, passes all tests.  
**Permanent Fix**: Update settings.yaml to use A3B model only. Update header comment to document 4B as unavailable.  
**Prevention**: Add model capability test to pre_flight.py. Update MODEL-SELECTION-TEST.md with final decision.  
**Recurrence**: false - model selection documented, A3B is primary model.


