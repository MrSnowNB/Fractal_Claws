---
title: Native Toolbox Policy
version: "1.0"
scope: global
applies_to: all_agents
---

# Native Toolbox Policy

## Tool Registry

All tools are declared in `tools/toolbox.yaml`. The agent may only call tools present
in the registry AND available at its current `agent.stage` (see `00-policy.md`).

Tool call format mirrors OpenClaw / Claude tool_use:

```
TOOL: <tool_name>
PATH: <argument>        ← file path, or primary argument
[CONTENT:
<body>
END]
```

The parser in `child_agent.py` resolves tool name → implementation via `toolbox.yaml`.
Unknown tools return `ERROR: unknown tool` and do not halt the agent.

## Stage-Gated Access

| Stage   | Tools Available                                          |
|---------|----------------------------------------------------------|
| bud     | read_file, write_file, exec_python                       |
| branch  | + shell, web_fetch                                       |
| planted | + graphify (knowledge graph over tickets/closed/)        |
| rooted  | full toolbox, including memory_write, memory_read        |

The toolbox loader in `agent/child_agent.py` filters by `agent.stage` from `settings.yaml`.
A bud-stage bot calling `graphify` receives: `ERROR: tool graphify not available at stage bud`.

## Adding New Tools

1. Create implementation in `tools/core/` (bud) or `tools/extended/` (branch+)
2. Add entry to `tools/toolbox.yaml` with `name`, `path`, `stage`, `description`, `risk`
3. Update this file's stage table above
4. Human approves before tool becomes active

## Long-Term Tools (Planted+)

### graphify
- Source: https://github.com/safishamsi/graphify
- Purpose: Build knowledge graphs from unstructured text (ticket logs, results, code)
- Use case: A planted bot running graphify over `tickets/closed/` builds a persistent
  world model — structured memory of what was tried, what failed, what succeeded.
- Risk: high (writes graph files, external dependency)
- Install: `pip install graphify` or local clone into `tools/extended/graphify/`

### memory_write / memory_read (Rooted)
- Purpose: Cross-session persistent state
- Storage: `logs/memory.yaml`
- A rooted bot can read its own history and prune failed branches autonomously
