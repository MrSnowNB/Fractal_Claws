---
name: sub-agent-task
description: >
  Delegate a bounded task to the LFM2.5-1.2B sub-agent running on the NPU via
  Lemonade. Use when the orchestrator needs to offload a fast, well-scoped task
  such as file formatting, YAML validation, doc generation, log summarization,
  or repetitive code transforms. Do not use for reasoning-heavy or multi-step tasks.
version: "1.0"
last_updated: "2026-04-01"
---

# sub-agent-task

## Purpose

Delegate atomic, bounded tasks from the Qwen3.5-35B orchestrator to the
LFM2.5-1.2B-Instruct-FLM sub-agent running on the XDNA 2 NPU via FastFlowLM.
Sub-agents run on separate hardware — NPU vs GPU — so delegation costs zero
orchestrator context and adds zero VRAM pressure.

Sub-agents are fast and cheap. Use them aggressively for work that does not
require deep reasoning.

---

## When to Delegate vs. Keep

| Task Type | Delegate to LFM2.5? | Reason |
|-----------|-------------------|--------|
| Format a Markdown file | ✅ Yes | Mechanical, bounded |
| Validate YAML frontmatter fields | ✅ Yes | Pattern match, no reasoning |
| Summarize a log file | ✅ Yes | Extractive, short output |
| Generate boilerplate from a template | ✅ Yes | Fill-in, no decisions |
| Write repetitive code transforms | ✅ Yes | Mechanical edits |
| Append a row to a Markdown table | ✅ Yes | Bounded insert |
| Lint error triage (classify only) | ✅ Yes | Match to known patterns |
| Design system architecture | ❌ No | Requires deep reasoning |
| Write SPEC.md from scratch | ❌ No | Requires full context |
| Debug a novel error | ❌ No | Multi-step reasoning needed |
| Make lifecycle phase decisions | ❌ No | Policy enforcement — orchestrator only |
| Anything touching ISSUE.md or TROUBLESHOOTING.md | ❌ No | Living docs — orchestrator owns |

---

## Pre-Flight Check

Before delegating, verify Lemonade has both models resident:

```powershell
curl http://localhost:8000/api/v1/models
```

Expected response includes both:
- `Qwen3.5-35B-A3B-GGUF` (GPU)
- `LFM2.5-1.2B-Instruct-FLM` (NPU / FastFlowLM)

If LFM2.5 is missing, Lemonade was started without `--max-loaded-models 2`.
Do not attempt delegation — trigger the troubleshoot skill instead.

Write the selected sub-agent port to `runtime.yaml` if not already present:

```yaml
---
title: ClawBot Runtime Config
last_updated: "<YYYY-MM-DD HH:MM>"
---
lemonade_base_url: "http://localhost:8000/api/v1"
orchestrator_model: "Qwen3.5-35B-A3B-GGUF"
sub_agent_model: "LFM2.5-1.2B-Instruct-FLM"
```

---

## Task Specification Format

Every sub-agent call must be fully self-contained. LFM2.5 has no access to
orchestrator context, prior conversation, or project files unless explicitly passed.

**Always include in the prompt:**

```
TASK: <one sentence — exactly what to do>
INPUT: <paste the full content or file path to read>
OUTPUT FORMAT: <Markdown with frontmatter | pure YAML | plain text>
SUCCESS CONDITION: <binary — what does done look like?>
CONSTRAINTS:
  - Do not infer or add content beyond what is specified
  - Do not modify files — return output only
  - If uncertain, return: "UNCERTAIN: <reason>"
```

**Example — YAML frontmatter validation:**

```
TASK: Validate that this Markdown file has all required frontmatter fields.
INPUT:
---
title: Gate Status Report
version: "1.0"
---
# content here
OUTPUT FORMAT: plain text
SUCCESS CONDITION: List any missing required fields. Required fields: title, version, last_updated.
CONSTRAINTS:
  - Do not modify the file
  - If all fields present, respond: "VALID"
  - If fields missing, respond: "MISSING: <field1>, <field2>"
```

---

## Calling the Sub-Agent

Use the OpenAI-compatible endpoint with explicit model selection:

```powershell
curl http://localhost:8000/api/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer lemonade" `
  -d '{
    "model": "LFM2.5-1.2B-Instruct-FLM",
    "messages": [{"role": "user", "content": "<task spec here>"}],
    "temperature": 0.1,
    "max_tokens": 512
  }'
```

**Settings:**
- `temperature: 0.1` — sub-agent tasks are deterministic; low temperature reduces drift
- `max_tokens: 512` — bounded output; if the task needs more, it is not a sub-agent task
- Never pass `stream: true` — collect full response before validation

---

## Output Validation

Before using sub-agent output, the orchestrator must validate:

1. **Format check** — does the output match the requested format (YAML/Markdown/text)?
2. **Uncertainty check** — does the output contain `"UNCERTAIN:"` ? If yes, do not use it — handle in orchestrator
3. **Length check** — did the response hit `max_tokens`? If truncated, re-run with a smaller input or split the task
4. **Content spot-check** — does the output make sense given the input? One-sentence sanity check

If validation fails on any point:
- Do not write the output to a file
- Re-run with a clarified task spec (one retry only)
- If still failing after one retry — handle in orchestrator or trigger troubleshoot skill

---

## Swap Testing

This skill supports model swap benchmarking as defined in the ClawBot planning phase.
To test a different sub-agent model, update `runtime.yaml` and re-run the same task spec:

```yaml
sub_agent_model: "Qwen3-Coder-Next-GGUF"  # swap for comparison
```

Record results in `REPLICATION-NOTES.md` under a **Model Swap Results** table:

```markdown
| Task | LFM2.5 Result | Alt Model Result | Winner | Notes |
|------|--------------|-----------------|--------|-------|
| YAML validate | VALID (0.4s) | VALID (1.2s) | LFM2.5 | 3x faster on NPU |
```

---

## Output Format

Sub-agent output is passed back to the orchestrator as a string.
The orchestrator writes any file outputs — sub-agents never write files directly.
All files written from sub-agent output must comply with `01-file-format.md`.
