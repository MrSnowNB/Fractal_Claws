---
title: AGENT-POLICY.md
version: "2.1"
scope: single-parent / single-child ticket harness
---

# AGENT-POLICY.md

## Endpoint Config

Configured entirely in `settings.yaml`:

```yaml
model:
  id: <model-id>         # set this for your inference server
  endpoint: <url>        # openai-compatible endpoint
  temperature: 0.2
  context_window: 8192
  timeout_seconds: 120
  max_retries: 3
```

**No model names in code or docs. Endpoint is frozen per session.**

---

## Roles

| Role | Who | Tools |
|------|-----|-------|
| Parent | Cline in VS Code | shell, read_file, write_file, list_dir |
| Child | runner.py (harness) | read_file, write_file, exec_python, list_dir |

---

## Forbidden Tools (Both Roles)

- `browser`
- `web_fetch`
- `computer_use`
- `code_interpreter`
- `shell` (child only — parent may use shell to invoke runner)

If a task requires a browser or web fetch: reject it. Write ISSUE.md. Halt.

---

## Lifecycle

```
Plan → Ticket → Spawn → Result → Validate → Done
```

| Phase | Who | Action |
|-------|-----|--------|
| Plan | Parent | Understand task, write ticket YAML |
| Ticket | Parent | Write to `tickets/open/` |
| Spawn | Parent | `python agent/runner.py --once` or `--goal` |
| Result | Runner | Read context, execute tools, write result, close ticket |
| Validate | Parent | Run 4 gates |
| Done | Parent | Confirm all gates green |

---

## Audit Log (JSONL)

Every attempt appends one line to `logs/<ticket_id>-attempts.jsonl`:

```json
{"ts": "...", "attempt": 1, "outcome": "pass", "tokens": 412, "elapsed_s": 3.2, "finish": "stop"}
```

Append-only. Never rewrite. Format: JSONL (not JSON) — one object per line.

---

## Validation Gates

```bash
pytest -q tests/
ruff check src/
mypy src/
python tools/spec_check.py
```

All four must pass. Any failure → failure procedure → halt.

---

## Failure Procedure

1. `TROUBLESHOOTING.md` — append entry with error, context, fix
2. `REPLICATION-NOTES.md` — append session delta
3. `ISSUE.md` — create/update with task text + rejection reason
4. Halt. Do not retry. Do not speculate. Await human.

---

## Ticket Rules

- Max 5 sentences per `task` field — keep within context budget
- `context_files` must exist before ticket is written
- `result_path` must be set before runner is invoked
- `decrement` starts at 3; hit 0 → status: escalated → halt

---

## Context Budget

Token budget is derived from `context_window` in `settings.yaml` (not from `max_tokens`):
- `BUDGET_CEILING` = 40% of `context_window` for execution
- `decompose_budget` = 25% of `context_window` (if not set explicitly)
- 80% context used: write `CHECKPOINT.md`, halt, alert human
