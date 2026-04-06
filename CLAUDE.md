---
title: CLAUDE.md — Fractal Claws POC
version: "2.0"
scope: 4B single-model child-agent POC
---

# CLAUDE.md

> Cline reads this file before every task. One model. One job. No swarms.

---

## What This Harness Is

A **4B model coding harness** where:
- Cline (in VS Code) is the **parent** — it reads tickets, writes code, calls tools
- A spawned `child_agent.py` is the **child** — it gets a ticket, uses read/write tools only, writes a result, exits
- The ticket YAML is the **only** contract between parent and child
- Success = child completes a ticket loop end-to-end with read_file + write_file

**One model. Two roles. No model switching. No swarms.**

---

## Model

```
Model:    Qwen3.5-4B-GGUF
Endpoint: http://localhost:11434/v1
Format:   openai-compat
```

Do not load any other model. Do not switch models mid-session.

---

## Parent Role (Cline)

1. Read task from human
2. Write a ticket YAML to `tickets/open/` using `tickets/template.yaml` as schema
3. Run: `python agent/child_agent.py tickets/open/<ticket>.yaml`
4. Poll `tickets/closed/` for result file
5. Read result, continue work or write next ticket
6. Run validation gates before declaring done

**Forbidden tools for parent:**
- `browser`, `web_fetch`, `computer_use`, `code_interpreter`
- Any tool not in: `shell`, `read_file`, `write_file`, `list_dir`

---

## Child Role (child_agent.py)

- Receives exactly one ticket YAML via `argv[1]`
- Reads `context_files` listed in the ticket using `tools/read_file.py`
- Writes result to `result_path` using `tools/write_file.py`
- Moves ticket to `tickets/closed/`
- Exits 0 on success, 1 on failure

**Child has exactly two tools: `read_file` and `write_file`. Nothing else.**

---

## Ticket Lifecycle

```
tickets/open/       <- parent writes here
tickets/in_progress/ <- child moves ticket here on pickup
tickets/closed/     <- child writes result, moves ticket here
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

**Max retries before halt: 2.** YOLO mode kills at 3 — stop at 2.

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
4. Never write to `tickets/closed/` directly — child does that.
5. Context at 80%: write `CHECKPOINT.md`, halt, alert human.
