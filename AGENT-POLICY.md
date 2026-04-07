---
title: AGENT-POLICY.md
version: "3.1"
scope: single-parent / single-child ticket harness
---

# AGENT-POLICY.md

## Endpoint Config

Configured entirely in `settings.yaml`:

```yaml
model:
  id: <model-id>         # child executor — currently A3B
  endpoint: <url>        # openai-compatible endpoint
  temperature: 0.2
  context_window: 64000
  timeout_seconds: 180
  max_retries: 3
```

**No model names in code or docs. Endpoint is frozen per session.**

---

## Roles

| Role | Who | Model | Tools |
|------|-----|-------|-------|
| Parent | Cline in VS Code | Qwen3-Coder-Next-GGUF (~80B) | shell, read_file, write_file, list_dir |
| Child | runner.py (harness) | Qwen3.5-35B-A3B-GGUF (A3B) | read_file, write_file, exec_python, list_dir |

> **4B Model: DEPRECATED** — Qwen3.5-4B-GGUF is deferred to a future integration phase.

---

## Forbidden Tools (Both Roles)

- `browser`, `web_fetch`, `computer_use`, `code_interpreter`
- `shell` (child only — parent may use shell to invoke runner)

If a task requires a browser or web fetch: reject it. Write ISSUE.md. Halt.

---

## Lifecycle

```
Plan → Ticket → Push → Spawn → Result → Validate → Done
```

| Phase | Who | Action |
|-------|-----|--------|
| Plan | Parent (Cline) | Understand task, decompose into tickets |
| Ticket | Parent | Write to `tickets/open/`, git push |
| Spawn | Parent | `python agent/runner.py --no-prewarm` |
| Result | Runner (A3B) | Read context, execute tools, write result + JSONL log, close ticket |
| Validate | Parent | Read `harness_result.json`, run 4 gates, check attempt logs |
| Done | Parent | All gates green, attempt logs have `outcome: pass` for all tickets |

---

## Handoff Metadata (Mandatory — v3.1)

Every ticket execution appends one JSONL line to `logs/<ticket_id>-attempts.jsonl`.
This log is the audit trail for:
- Parent verification (reading attempt logs to confirm child completed correctly)
- Triage when a multi-ticket chain fails mid-run
- Performance monitoring (tok/s, elapsed_s, budget utilization)

### JSONL schema

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

`outcome` values: `pass` | `fail` | `error`  
`finish` values: `stop` | `length` | `content_filter` | `unknown`

---

## Audit Log (JSONL)

Append-only. Never rewrite. One object per line.  
Path: `logs/<ticket_id>-attempts.jsonl`  
Gitignored (runtime data, not committed).

---

## Validation Gates

```bash
pytest -q tests/
ruff check src/
mypy src/
python tools/spec_check.py
```

All four must pass. Any failure → failure procedure → halt.

For harness integration test specifically, also run:
```bash
pytest -q tests/test_harness_artifacts.py
```

---

## Failure Procedure

1. `TROUBLESHOOTING.md` — append entry with error, context, fix
2. `REPLICATION-NOTES.md` — append session delta
3. `ISSUE.md` — create/update with task text + rejection reason
4. Halt. Do not retry. Do not speculate. Await human.

---

## Ticket Rules

- Minimum 3 sentences per `task` field (thinking-model needs full context)
- `context_files` must exist before ticket is written
- `result_path` must be set before runner is invoked
- `attempts_log` must be set to `logs/<ticket_id>-attempts.jsonl`
- `decrement` starts at 3; hit 0 → status: escalated → halt
- Always check all three ticket dirs for max ID before assigning new ticket_id
- All `.py` output paths must use `output/` prefix — never bare filenames

---

## Context Budget

- `BUDGET_FLOOR` = 1024 tokens (minimum for thinking pass + tool block)
- `BUDGET_CEILING` = `context_window * output_budget_pct` (80% = 51200)
- `token_budget()` multiplier = `*24` (thinking model headroom)
- 80% context used: write `CHECKPOINT.md`, halt, alert human
