---
title: Qwen3.5-4B Parent Agent Rules
version: "2.0"
scope: workspace
applies_to: parent_agent
model: Qwen3.5-4B-GGUF
hardware: HP ZBook (single node)
endpoint: http://localhost:8000/api/v1
---

# Qwen3.5-4B Parent Agent Rules

## Hardware and Endpoint

```
Machine:  HP ZBook (single node)
Endpoint: http://localhost:8000/api/v1
API key:  x
Model:    Qwen3.5-4B-GGUF
```

This is NOT a Z8. Do not use port 11434. Lemonade runs on :8000 here.
One model only. No 35B, no Hermes, no LFM2.5, no swarm.

## Thinking Budget

- Plan phase: think blocks allowed for ticket decomposition
- Build phase: suppress thinking, append /no_think
- All other phases: no thinking

## Tool Call Discipline

- One tool call per turn, wait for result
- Max retries: 2 - on second failure write ISSUE.md and halt
- YOLO kills at 3 - stop at 2

## Forbidden Actions

- Do NOT pip install anything
- Do NOT register or start MCP servers
- Do NOT modify Cline config or VSCode settings
- Do  use browser, web_fetch, or computer_use
- Do NOT spawn more than one child per ticket
- Do NOT write to tickets/closed/ directly

## Sub-Agent Delegation

1. Write ticket YAML to tickets/open/ using tickets/template.yaml
2. Verify context_files exist
3. Verify result_path is set
4. Run: python agent/child_agent.py tickets/open/<id>.yaml
5. Poll tickets/closed/<id>.yaml for status
6. Read result_path for output

Child tools: read_file and write_file ONLY.

## Context Management

- 60%: write CHECKPOINT.md, continue
- 80%: halt, alert human

## Response Format

- All file outputs: Markdown with YAML frontmatter, or pure YAML
- No raw JSON or plain text deliverables
- No markdown inside ticket task fields
