---
title: AGENT-POLICY.md
version: "2.0"
scope: 4B single-model child-agent POC
---

# AGENT-POLICY.md

## Model

```yaml
model:    Qwen3.5-4B-GGUF
endpoint: http://localhost:11434/v1
format:   openai-compat
temp:     0.2
max_tokens: 512
timeout:  90s
retries:  2  # stop BEFORE yolo-mode kills at 3
```

**One model. One endpoint. Frozen for this POC.**

---

## Roles

| Role | Who | Tools |
|------|-----|-------|
| Parent | Cline in VS Code | shell, read_file, write_file, list_dir |
| Child | child_agent.py (subprocess) | read_file, write_file ONLY |

---

## Forbidden Tools (Both Roles)

- `browser`
- `web_fetch`
- `computer_use`
- `code_interpreter`
- `shell` (child only — parent may use shell to spawn child)

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
| Spawn | Parent | `python agent/child_agent.py <ticket>` |
| Result | Child | Read context, write result, close ticket |
| Validate | Parent | Run 4 gates |
| Done | Parent | Confirm all gates green |

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

- Max 5 sentences per `task` field — 4B context budget
- `context_files` must exist before ticket is written
- `result_path` must be set before child is spawned
- `decrement` starts at 3; hit 0 → status: escalated → halt

---

## Context Budget

- 60%: write `CHECKPOINT.md`
- 80%: halt, alert human
- Never continue a task that cannot complete in remaining budget
