---
title: "Active Task Spec — Cline Coding Agent Context"
version: "1.0.0"
owner: "MrSnowNB"
status: "template — replace with active task before each session"
lifecycle_phase: "plan"
updated: "2026-04-05"
---

# CLAUDE.md — Active Task Spec

> **This file is the coding agent's north star for the current session.**
> Read `AGENT-POLICY.md` first. Then read this file completely before touching any code.
> Replace the TASK section below with the actual task before each session.

---

## Frozen Harness Config (DO NOT CHANGE during validation)

```yaml
model: qwen2.5-coder:7b          # or whichever passed H-1 through H-6 last
backend: lemonade                 # preferred; fallback: ollama
endpoint: http://localhost:11434/v1
tool_schema: cline_default        # do not modify schema during harness runs
cwd: /home/mr-snow/                # repo root
```

---

## Active Task

```yaml
task_id: "TASK-TEMPLATE"
description: "REPLACE WITH ONE SENTENCE TASK DESCRIPTION"
inputs:
  - "list input files or triggers"
outputs:
  - "list expected output files or artifacts"
acceptance_criteria:
  - "must pass H-1 through H-6 (5/5) before ticket spawning"
  - "pytest -q green"
  - "ruff check clean"
  - "mypy clean on modified files"
  - "REPLACE WITH TASK-SPECIFIC CRITERIA"
max_files_changed: 5
self_improvement_loop: false      # set true only after harness passes
ticket_spawning: false            # set true only after harness + loop validated
```

---

## Self-Improvement Loop Instructions (active only when self_improvement_loop: true)

1. Read the target file(s) listed in `inputs` above.
2. Identify **one specific, testable defect**. Write it down as a comment in your reasoning.
3. **Write a failing test first.** Name it `test_<defect_name>.py` in `tests/`.
4. Verify the test fails: `pytest tests/test_<defect_name>.py -q`
5. Write the minimal patch to make the test pass.
6. Run all four validation gates.
7. Append a loop iteration entry to `REPLICATION-NOTES.md` using the schema in `AGENT-POLICY.md`.
8. If gates pass: check for next defect. If no more defects, halt cleanly.
9. If gates fail: append to `TROUBLESHOOTING.md`, open `ISSUE.md`, halt.
10. **Halt after 3 consecutive gate failures. No exceptions.**

---

## Tool Use Rules (Cline Harness)

- Always execute tool calls as actual tool calls. Never output tool call JSON as plain text.
- After any write_file call, immediately verify with read_file. Confirm exact contents.
- After any shell call, return verbatim stdout in a code block. Do not paraphrase.
- After any tool call, append the role=tool result to message history before proceeding.
- Never write to paths outside the declared `cwd`.
- Never modify more than `max_files_changed` files per task.

---

## Ticket Spawning Instructions (active only when ticket_spawning: true)

Parent ticket writes to `tickets/open/TRIG-{UNIX_TIMESTAMP}.yaml` using the schema in
`AGENT-POLICY.md`. Child worker is spawned via:

```bash
python src/ticket_spawner.py --ticket tickets/open/TRIG-{id}.yaml
```

Child result is written to `tickets/results/TRIG-{id}.yaml`. Parent reads result and
proceeds or escalates based on `status` field.

---

## Session Checklist

Before starting any work, verify:

- [ ] `AGENT-POLICY.md` has been read completely
- [ ] Harness config above matches last known-good config in `REPLICATION-NOTES.md`
- [ ] `tickets/active/` is empty (no orphaned tickets from prior session)
- [ ] `pytest -q` runs without import errors (environment is healthy)
- [ ] `nvidia-smi` shows all 4 GPUs (if running GPU-backed models)
- [ ] Ollama/Lemonade endpoint is responding: `curl http://localhost:11434/v1/models`
