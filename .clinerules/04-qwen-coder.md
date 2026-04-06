---
title: Qwen3.5-4B — Parent Agent Rules
version: "2.0"
scope: workspace
applies_to: parent_agent
model: "Qwen3.5-4B-GGUF"
---

# Qwen3.5-4B Parent Agent Rules

## Model

This harness runs **one model only**: `Qwen3.5-4B-GGUF` via `http://localhost:11434/v1`.

Do not reference, load, or delegate to any other model. There is no 35B slot. There is no leaf/NPU slot. There is no swarm.

## Thinking Budget

- **Plan phase**: `<think>` blocks allowed — use for ticket decomposition only
- **Build phase**: Suppress thinking — append `/no_think` to tool instructions
- **All other phases**: No thinking blocks

Rationale: 4B context window is 8K tokens. Unconstrained thinking exhausts it before the task completes.

## Tool Call Discipline

- **One tool call per turn.** Wait for result before issuing next.
- Never chain tool calls speculatively.
- If result is ambiguous — stop, evaluate, then proceed.
- **Max retries: 2.** On the second failure, write ISSUE.md and halt. Do not attempt a third — YOLO mode terminates at 3.

## Forbidden Actions

- Do NOT install packages (`pip install`, `npm install`, etc.)
- Do NOT register or start MCP servers
- Do NOT modify Cline config files or VSCode settings (pre_flight.py handles this)
- Do NOT use browser, web_fetch, or computer_use tools
- Do NOT spawn more than one child per ticket
- Do NOT write to `tickets/closed/` directly — child_agent.py does that

## Sub-Agent Delegation

When spawning `agent/child_agent.py`:

1. Write a complete ticket YAML to `tickets/open/` using `tickets/template.yaml` as schema
2. Verify `context_files` exist before spawning
3. Verify `result_path` is set
4. Run: `python agent/child_agent.py tickets/open/<id>.yaml`
5. Poll `tickets/closed/<id>.yaml` for status
6. Read `result_path` for the output

Child has **two tools only**: `read_file` and `write_file`. Do not instruct it to do anything that requires a third tool.

## Context Management

- At 60% context: write `CHECKPOINT.md`, continue
- At 80% context: halt, alert human
- Never continue a task that cannot complete in remaining budget

## Response Format

- All file outputs: Markdown with YAML frontmatter, or pure YAML
- No raw JSON, plain text, or unstructured deliverables
- No markdown in the `task` field of a ticket YAML
