---
title: TROUBLESHOOTING Guide
version: "0.3.0"
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

### TS-20260407-002: 4B Model Empty Choices (Historical)

**Status**: DEPRECATED — NOT A BLOCKER ✅ 2026-04-07  
**Context**: Qwen3.5-4B-GGUF consistently fails decompose task with empty choices across multiple test runs.  
**Root Cause**: Model not loaded in Lemonade slot + no ctx_size in recipe_options + likely insufficient fine-tuning for structured YAML output.  
**Resolution**: 4B formally deprecated and deferred to future integration phase. Active harness uses Coder-Next (parent) + A3B (child). 4B is not a blocker — it was never part of the ticketing system test.  
**Recurrence**: N/A — model removed from active rotation.

---

### TS-20260407-003: Model Selection Finalized

**Status**: RESOLVED ✅ 2026-04-07  
**Context**: Final model assignment for ticketing system test phase.  
**Decision**:
  - Parent (Cline): Qwen3-Coder-Next-GGUF (~80B)
  - Child (runner.py): Qwen3.5-35B-A3B-GGUF
  - 4B: DEPRECATED — deferred to future leaf/worker integration
**Files updated**: settings.yaml, pre_flight.py, CLAUDE.md, AGENT-POLICY.md, MODEL-SELECTION-TEST.md, REPLICATION-NOTES.md  
**Recurrence**: false

---

### TS-20260407-004: 4B Formal Deprecation Notice

**Status**: DOCUMENTED ✅ 2026-04-07  
**Context**: During session review it was identified that multiple files still referenced or directed the agent toward Qwen3.5-4B-GGUF, causing Cline to repeatedly attempt 4B model calls instead of focusing on the ticketing system test.  
**Symptom**: Agent wasted cycles on 4B diagnosis; ticketing system test never started.  
**Root Cause**: Documentation (TROUBLESHOOTING.md, MODEL-SELECTION-TEST.md, settings.yaml header) framed 4B as an active issue to fix rather than a deferred future integration.  
**Fix**: All files updated in single commit to:
  - Hard-block 4B in pre_flight.py (exit 1 with deprecation message)
  - Set settings.yaml model.id = A3B, context_window = 64000
  - Remove 4B from KNOWN_MODELS in pre_flight.py (commented out)
  - Update all docs to frame 4B as DEPRECATED (future phase), not UNAVAILABLE (blocker)
**Prevention**: Any reference to Qwen3.5-4B-GGUF in active session docs must include the label `DEPRECATED — future integration`. Do not create TROUBLESHOOTING entries for deprecated models unless they surface in an active run.  
**Recurrence**: false

---

### TS-20260407-005: Runner Max Retries Policy Violation

**Status**: OPEN ❌ 2026-04-07  
**Context**: Runner.py executes model call exceeding retry limit per policy.  
**Symptom**: Model call failed after 4 attempts; deadlock reached (TASK-003 blocked on TASK-002).  
**Error Snippet**: 
```
[model] attempt 4: empty content — retry in 4s
[runner] model call failed: model call failed after 4 attempts
[runner] max_depth reached → failed/TASK-002.yaml
[runner] deadlock — 1 ticket(s) blocked on unmet deps:
  TASK-003 waiting on ['TASK-002']
```
**Probable Cause**: Configuration policy violation:
  - Policy states: "YOLO kills at 3 — stop at 2 retries"
  - settings.yaml had `max_retries: 3`
  - runner.py uses `range(1, MAX_RETRIES + 2)` = 4 attempts total
**Quick Fix**: Update settings.yaml `max_retries: 2`  
**Permanent Fix**: Add validation in pre_flight.py to check max_retries ≤ 2. Enforce policy compliance in CI/CD.  
**Prevention**: Add settings.yaml schema validation; run pre_flight.py before any runner invocation.  
**Recurrence**: false — root cause identified and fixed in settings.yaml

---

### TS-20260407-007: Runner Max Retries Exceeded (YOLO Policy)

**Status**: RESOLVED ✅ 2026-04-07  
**Context**: runner.py terminates after max_retries exceeded during TASK-001 execution.  
**Symptom**: `max_retries exceeded` error, runner exits 1.  
**Error Snippet**: 
```
[runner] model call failed: model call failed after 4 attempts  
[runner] max_retries exceeded
```
**Root Cause**: settings.yaml had `max_retries: 3` but policy requires `max_retries: 2` (YOLO kills at 3 — stop at 2).  
**Quick Fix**: Update settings.yaml `max_retries: 2`  
**Permanent Fix**: Add pre_flight.py validation to check max_retries ≤ 2; pre_flight now exits 1 if max_retries > 2.  
**Prevention**: Enforce settings.yaml schema validation; run pre_flight.py before any runner invocation.  
**Recurrence**: false — policy fixed and validated

---

### TS-20260407-006: exec_python Path Restriction Error

**Status**: OPEN ❌ 2026-04-07
**Context**: Child agent attempts to execute Python file outside allowed output/ directory.  
**Symptom**: `[tool] exec_python → fib.py` followed by `ERROR: exec_python blocked — path must be inside output/ (got fib.py)`  
**Probable Cause**: Ticket TASK-002 write_file created `fib.py` at project root, but exec_python only allows paths inside `output/`.  
**Quick Fix**: Update ticket task to write to `output/fib.py` instead of `fib.py`.  
**Permanent Fix**: Add path validation in child_agent.py exec_python tool to ensure path starts with `output/`. Add test case in conftest.py to verify path restriction.  
**Prevention**: Document path restriction in tickets/template.yaml comments; add path prefix validation.  
**Recurrence**: false — path restriction is intentional security feature
