---
title: ClawBot Agent Policy
version: "1.0"
scope: global
applies_to: all_agents
last_updated: "2026-04-01"
***

# ClawBot Agent Policy

## Core Mandates

All files produced by agents are **Markdown with YAML frontmatter** or **pure YAML**.
No other file formats may be created unless explicitly approved by the human operator.

Every task assigned to an agent must be:
- **Atomic** — one clear, bounded objective per task
- **Testable** — a binary pass/fail outcome must be definable before work begins
- **Gated** — the agent may not proceed to the next task until the current gate passes

On any failure **or** uncertainty, the agent must:
1. Update all living documents (`TROUBLESHOOTING.md`, `REPLICATION-NOTES.md`)
2. Open or update `ISSUE.md`
3. Call `halt_and_wait_human` — no speculative continuation

***

## Lifecycle (Sequential Only)

```
Plan → Build → Validate → Review → Release
```

No phase may be skipped. No phase may be revisited without explicit human instruction.
Each phase transition requires the previous phase's gate to be green.

| Phase    | Entry Condition                         | Exit Gate                          |
|----------|-----------------------------------------|------------------------------------|
| Plan     | Human approves task scope               | Spec written, reviewed by human    |
| Build    | Spec approved                           | All validation gates green         |
| Validate | Build complete                          | All four validation suites pass    |
| Review   | Validation green                        | Human approves diff                |
| Release  | Human approval received                 | Artifact tagged and documented     |

***

## Validation Gates

All four gates must be green before the Build→Validate→Review transition:

```yaml
gates:
  unit:
    command: "pytest -q"
    pass_condition: "0 failed, 0 errors"
  lint:
    command: "ruff check . || flake8 ."
    pass_condition: "clean output"
  type:
    command: "mypy . || pyright ."
    pass_condition: "0 errors"
  docs:
    command: "spec drift check"
    pass_condition: "no unresolved drift"
```

A single gate failure blocks the entire transition. The agent captures the failure, updates living docs, and halts.

***

## Failure Handling Procedure

When any step fails or the agent is uncertain:

```
1. capture_logs()           → save full stdout/stderr to logs/
2. update_troubleshooting() → append entry to TROUBLESHOOTING.md
3. update_replication()     → append entry to REPLICATION-NOTES.md
4. open_issue()             → create or update ISSUE.md
5. halt_and_wait_human()    → stop all work, await instruction
```

**No recovery attempts without human approval.**