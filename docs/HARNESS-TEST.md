# Fractal Claws — Harness Integration Test

**Version:** 1.0  
**Tickets:** TASK-008, TASK-009, TASK-010, TASK-011  
**Purpose:** End-to-end validation of the Cline → runner.py → executor pipeline
with multi-step dependency chaining, upstream context injection, and handoff
metadata logging at every stage.

---

## Overview

This test runs a four-ticket chain that exercises every critical harness component:

| Ticket | Stage | Tools | Depends On |
|--------|-------|-------|------------|
| TASK-008 | Data generation | write_file, exec_python | — |
| TASK-009 | Report generation | read_file, write_file | TASK-008 |
| TASK-010 | Metadata audit | read_file, write_file | TASK-009 |
| TASK-011 | Parent verification | read_file, write_file, exec_python | TASK-010 |

---

## How to Run

```powershell
# 1. Pull latest (tickets are in tickets/open/ on main)
git pull

# 2. Run the drain
python agent/runner.py --no-prewarm

# 3. Assert artifacts and logs
pytest -q tests/test_harness_artifacts.py
```

Expected final line: `[runner] all tickets closed — done`

---

## Expected Artifacts

After a clean run, these files must exist:

| File | Written By | Content Contract |
|------|------------|------------------|
| `output/word_freq.py` | TASK-008 | Python script; stdout contains `the: 5` |
| `output/report.md` | TASK-009 | Markdown; contains `## Top Words` |
| `output/audit.json` | TASK-010 | JSON; `test_run == "harness-integration-v1"`, `report_contains_top_words == true` |
| `output/harness_result.json` | TASK-011 | JSON; `passed == true`, `failed_checks == []` |
| `output/verify_harness.py` | TASK-011 | Python verification script |

---

## Expected Attempt Logs

Every ticket writes a JSONL attempt log. These must exist after the run:

| File | Schema |
|------|--------|
| `logs/TASK-008-attempts.jsonl` | One line per attempt, `outcome: pass` on final |
| `logs/TASK-009-attempts.jsonl` | One line per attempt, `outcome: pass` on final |
| `logs/TASK-010-attempts.jsonl` | One line per attempt, `outcome: pass` on final |
| `logs/TASK-011-attempts.jsonl` | One line per attempt, `outcome: pass` on final |

### JSONL Line Schema

```json
{
  "ts":          "2026-04-07T13:45:00",
  "ticket_id":   "TASK-008",
  "attempt":     1,
  "outcome":     "pass",
  "tokens":      528,
  "elapsed_s":   15.26,
  "tok_s":       34.6,
  "finish":      "stop",
  "budget":      3296,
  "tool_calls":  2,
  "reason":      "ok",
  "ram_pre_gb":  98.27,
  "ram_post_gb": 99.1,
  "cpu_pre_pct": 4.0
}
```

---

## Failure Triage

### TASK-008 fails
- Check `logs/TASK-008-result.txt` for `=== raw model response` section
- Look for `ERROR:` in tool results — likely a path violation (bare filename instead of `output/`)
- Check `logs/TASK-008-attempts.jsonl` — if `tool_calls: 0`, the model produced no tool blocks (budget too low or empty content retry)
- Fix: increase `timeout_seconds` in `settings.yaml` if `finish: length`

### TASK-009 fails
- Check `deps_context=yes` in console output — if `no`, upstream context injection failed
- Check `logs/TASK-008-result.txt` exists and has content after `=== tool results ===`
- If report.md exists but has no `## Top Words`: model ignored upstream context; retry

### TASK-010 fails
- Check `output/report.md` exists and is non-empty
- If `report_contains_top_words: false` in audit.json: TASK-009 produced malformed report
- Cascade failure — fix TASK-009 first, then re-run from TASK-010

### TASK-011 fails
- Check `output/harness_result.json` for `failed_checks` list
- Check each failed check against its source ticket
- If attempt logs missing: runner.py `append_attempt_log` not firing — check runner version

### All tickets fail immediately (no tool calls)
- Model returning empty content repeatedly — Lemonade endpoint issue
- Run `python pre_flight.py` to check endpoint health
- Check `settings.yaml` model.id matches loaded model in Lemonade

---

## Handoff Metadata Flow

```
TASK-008 executes
  └─ writes output/word_freq.py
  └─ executes it, stdout captured in logs/TASK-008-result.txt
  └─ appends to logs/TASK-008-attempts.jsonl  ←─ NEW in v5
  └─ closed → tickets/closed/TASK-008.yaml

TASK-009 dispatched (deps_context=yes)
  └─ runner injects TASK-008 result.txt into prompt
  └─ writes output/report.md
  └─ appends to logs/TASK-009-attempts.jsonl  ←─ NEW in v5
  └─ closed → tickets/closed/TASK-009.yaml

TASK-010 dispatched (deps_context=yes)
  └─ runner injects TASK-009 result.txt (contains report.md path)
  └─ reads output/report.md, writes output/audit.json
  └─ appends to logs/TASK-010-attempts.jsonl  ←─ NEW in v5
  └─ closed → tickets/closed/TASK-010.yaml

TASK-011 dispatched (deps_context=yes)
  └─ writes + executes output/verify_harness.py
  └─ verify_harness.py reads all artifacts + attempt logs
  └─ writes output/harness_result.json
  └─ appends to logs/TASK-011-attempts.jsonl  ←─ NEW in v5
  └─ closed → tickets/closed/TASK-011.yaml
```

---

## Passing Criteria

- `[runner] all tickets closed — done` in console
- `pytest -q tests/test_harness_artifacts.py` — all tests green
- `output/harness_result.json` — `passed: true`, `failed_checks: []`
- All four `*-attempts.jsonl` files exist with at least one `outcome: pass` line
