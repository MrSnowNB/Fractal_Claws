---
title: Cline Parent Agent Rules (Qwen3-Coder-Next)
version: "3.0"
scope: workspace
applies_to: parent_agent
model: Qwen3-Coder-Next-GGUF
hardware: HP ZBook (single node)
endpoint: http://localhost:8000/api/v1
---

# Cline Parent Agent Rules

> Cline is the **parent orchestrator**. It writes tickets and spawns runner.py.
> runner.py (child) calls the A3B model to execute tickets.
> **4B model: DEPRECATED** — deferred to future integration phase. Do not reference or load it.

---

## Hardware and Endpoint

```
Machine:  HP ZBook (single node)
Endpoint: http://localhost:8000/api/v1
API key:  x
Parent:   Qwen3-Coder-Next-GGUF  (~80B, Cline orchestrator)
Child:    Qwen3.5-35B-A3B-GGUF   (runner.py executor)
```

This is NOT a Z8. Do not use port 11434. Lemonade runs on :8000 here.
Model config is in settings.yaml — do not hardcode model names in code.

---

## Thinking Budget

- Plan phase: think blocks allowed for ticket decomposition
- Build phase: suppress thinking, append /no_think
- All other phases: no thinking

---

## Tool Call Discipline

- One tool call per turn, wait for result
- Max retries: 2 — on second failure write ISSUE.md and halt
- YOLO kills at 3 — stop at 2

---

## Forbidden Actions

- Do NOT pip install anything
- Do NOT register or start MCP servers
- Do NOT modify Cline config or VSCode settings
- Do NOT spawn more than one child per ticket
- Do NOT write to tickets/closed/ directly
- Do NOT reference, load, or test Qwen3.5-4B-GGUF

---

## Child Delegation (runner.py)

1. Write ticket YAML to `tickets/open/` using `tickets/template.yaml`
2. Verify `context_files` exist
3. Verify `result_path` is set
4. Run: `python agent/runner.py --once`
5. Poll `tickets/closed/<id>.yaml` for status
6. Read `result_path` for output

Child tools: `read_file`, `write_file`, `exec_python`, `list_dir`. Nothing else.

---

## Context Management

- 60%: write CHECKPOINT.md, continue
- 80%: halt, alert human

---

## Response Format

- All file outputs: Markdown with YAML frontmatter, or pure YAML
- No raw JSON or plain text deliverables
- No markdown inside ticket task fields
