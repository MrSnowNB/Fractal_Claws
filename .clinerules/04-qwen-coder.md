---
title: Qwen3-Coder-Next Orchestrator Rules
version: "1.0"
scope: workspace
applies_to: orchestrator
model: "Qwen3-Coder-Next-GGUF"
---

# Qwen3-Coder-Next Orchestrator Rules

## Thinking Budget

- **Plan phase**: Full `<think>` blocks enabled — required for task decomposition and spec drafting
- **Build phase**: Suppress thinking for file writes and terminal commands — append `/no_think` to tool instructions
- **Validate phase**: Enable thinking only when interpreting ambiguous gate output
- **Review and Release**: No thinking required — responses are bounded and factual

Rationale: `<think>` blocks consume context at ~4-8x the rate of direct output. On a 128K context window, unconstrained thinking in Build phase exhausts the budget before the task completes.

## Tool Call Discipline

- Issue **one tool call at a time** — wait for the result before issuing the next
- Never chain tool calls speculatively
- If a tool call result is ambiguous, evaluate before proceeding — do not assume success

## Context Management

- At 60% context utilization: write a checkpoint summary to `CHECKPOINT.md` and continue
- At 80% context utilization: halt, summarize state to `CHECKPOINT.md`, alert human
- Never attempt to continue a task that cannot be completed within the remaining context budget

## Sub-Agent Delegation

When delegating to LFM2.5 sub-agents:
- Pass a fully-specified task description — sub-agents do not have access to prior orchestrator context
- Include the relevant file paths, expected output format (Markdown/YAML), and success criteria
- Sub-agent output must be validated before the orchestrator uses it

## Response Format

- All responses to the human are in Markdown
- All file outputs comply with the file format policy (00-policy.md)
- Never produce raw JSON, plain text, or unstructured output as a deliverable
