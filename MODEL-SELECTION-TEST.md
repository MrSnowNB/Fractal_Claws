---
title: "Model Selection Test Results"
version: "2026-04-07-v2"
last_updated: "2026-04-07"
---

# Model Selection Test Results

## Final Decision: A3B as child executor. Coder-Next as parent (Cline).

---

## Harness Model Map

| Role | Model | ctx_size | Status |
|------|-------|----------|--------|
| Parent (Cline orchestrator) | Qwen3-Coder-Next-GGUF | 64,000 | ✅ Active |
| Child (runner.py executor) | Qwen3.5-35B-A3B-GGUF | 64,000 | ✅ Active |
| Future leaf/worker (deferred) | Qwen3.5-4B-GGUF | TBD | ⛔ DEPRECATED — do not use |

---

## 4B Model Test Results (Historical — do not re-run)

| Model | ID | Status | Issue |
|-------|-----|--------|-------|
| Qwen3.5-4B-GGUF | Qwen3.5-4B-GGUF | **DEPRECATED** | Empty choices on decompose; deferred to future integration |

### Observed Behavior (4B Model — archived)
- Model call returns `empty choices` consistently across all retry attempts
- 4 retry attempts exhausted before failure
- Decompose phase fails — cannot produce valid YAML output
- Root cause: no `ctx_size` in recipe_options + likely insufficient fine-tuning for structured output

### Why 4B is Deprecated (not just unavailable)
The 4B failure is a **scope issue, not a blocker**. The current test goal is to validate the
ticket harness end-to-end with the Coder-Next → A3B parent/child pair. The 4B was never
part of that test. It is preserved for a future phase where small leaf/worker models
are integrated as subordinate executors.

---

## A3B End-to-End Test Results (2026-04-07)

### Test Command
```powershell
python agent/runner.py --goal "write a python script that generates the first 20 fibonacci numbers and saves them to output/fib.txt, then verify the file was written"
```

### Result: PASS ✅
- 8 tickets decomposed and closed
- All PASS
- Decompose: 609 tokens, 10.43s
- Fastest: TASK-017, 1.66s @ 121.7 tok/s
- Slowest: TASK-015, 7.75s @ 54.7 tok/s
- RAM stable: ~98.6 GB / 127 GB

---

## Active Configuration

```yaml
model:
  id: Qwen3.5-35B-A3B-GGUF    # child executor
  endpoint: http://localhost:8000/api/v1
  timeout_seconds: 180
  max_retries: 3
  decompose_budget: 2048
  context_window: 64000
```

---

## Next Test: Ticketing System Validation

Goal: Cline (Coder-Next parent) spawns A3B child via runner.py to complete a series
of tickets that solve a real problem end-to-end. Validate:
- Ticket lifecycle (open → in_progress → closed)
- Dependency chain (depends_on)
- Result forwarding (upstream context injection)
- All 4 validation gates green
