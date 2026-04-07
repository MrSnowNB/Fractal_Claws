---
title: CLAUDE.md — Fractal Claws POC
version: "2.1"
scope: single-parent / single-child ticket harness
---

# CLAUDE.md

> Cline reads this file before every task. One harness. Two roles. No swarms.

---

## What This Harness Is

A **model-agnostic coding harness** where:
- Cline (in VS Code) is the **parent** — it reads tickets, writes code, calls tools
- `agent/runner.py` is the **child harness** — it receives a ticket, uses read/write/exec tools, writes a result, exits
- The ticket YAML is the **only** contract between parent and child
- Success = child completes a ticket loop end-to-end and writes a result file

The model and endpoint are defined in `settings.yaml`. This file contains no model names.

**One harness. Two roles. No model switching. No swarms.**

---

## Endpoint Config

See `settings.yaml`:
```yaml
model:
  id: <your-model-id>
  endpoint: <your-openai-compat-endpoint>
```

Do not hardcode model names in code or docs.

---

## Parent Role (Cline)

1. Read task from human
2. Write a ticket YAML to `tickets/open/` using `tickets/template.yaml` as schema
3. Run: `python agent/runner.py --once` (single ticket) or `--goal "<goal>"` (decompose + drain)
4. Poll `tickets/closed/` or `logs/` for result file
5. Read result, continue work or write next ticket
6. Run validation gates before declaring done

**Forbidden tools for parent:**
- `browser`, `web_fetch`, `computer_use`, `code_interpreter`
- Any tool not in: `shell`, `read_file`, `write_file`, `list_dir`

---

## Child Role (runner.py)

- Receives tickets from `tickets/open/`
- Reads `context_files` listed in the ticket
- Executes tool calls (read_file, write_file, exec_python, list_dir)
- Writes result to `logs/<ticket_id>-result.txt`
- Appends one JSONL record to `logs/<ticket_id>-attempts.jsonl` per attempt
- Moves ticket to `tickets/closed/` on pass, `tickets/failed/` on max depth
- Exits 0 on full queue drain, 1 on unrecoverable failure

**Child tools: `read_file`, `write_file`, `exec_python`, `list_dir`. Nothing else.**

---

## Ticket Lifecycle

```
tickets/open/        <- parent writes here
tickets/in_progress/ <- runner moves ticket here on pickup
tickets/closed/      <- runner closes ticket here on pass
tickets/failed/      <- runner moves ticket here on max depth
logs/<id>-result.txt <- result written here by runner
logs/<id>-attempts.jsonl <- JSONL audit log, one line per attempt
```

---

## Validation Gates

All four must be green before any task is "done":

| Gate | Command | Pass |
|------|---------|------|
| Unit | `pytest -q tests/` | 0 failures |
| Lint | `ruff check src/` | clean |
| Type | `mypy src/` | 0 errors |
| Docs | `python tools/spec_check.py` | no drift |

---

## Failure Procedure

1. Append to `TROUBLESHOOTING.md`
2. Append to `REPLICATION-NOTES.md`
3. Write `ISSUE.md`
4. Halt. Do not retry. Wait for human.

**Max retries before halt: 2.** Stop at 2 — YOLO mode kills at 3.

---

## Session Startup Checklist

```bash
python pre_flight.py
```

If any check fails — fix it before accepting any task.

---

## Rules

1. One tool call per turn. Wait for result.
2. Never narrate. Never explain. Call the tool, then stop.
3. Never spawn more than one child per ticket.
4. Never write to `tickets/closed/` directly — runner does that.
5. Context at 80%: write `CHECKPOINT.md`, halt, alert human.
