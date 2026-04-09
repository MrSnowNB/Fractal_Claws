---
title: BuddingBot Agent Policy
version: "2.0"
scope: global
applies_to: all_agents
last_updated: "2026-04-06"
---

# BuddingBot Agent Policy

## HARD BEHAVIORAL INVARIANTS (added 2026-04-09)

These rules are NON-NEGOTIABLE. Violating any of them is a gate failure.

1. **NEVER skip journal entries.** Every completed step MUST have a journal
   entry written to `logs/luffy-journal.jsonl` before moving to the next step.
   Use `append_journal()` or the SequenceGate. No exceptions.

2. **NEVER skip git commit.** After every completed step, `git add` all changed
   files + journal, then `git commit -m "STEP-XX: summary"`. If commit fails,
   fix the issue and retry. Do NOT proceed to the next step with uncommitted work.

3. **Check context budget before reading files.** Before reading any context_file
   or spec document, check `ContextBudget.should_read()`. If the file is cached
   and unchanged, use the summary instead of re-reading the full content.
   Log skips: `[ctx] SKIP {path} — cached, ~{tokens} tokens saved`

These rules exist because Luffy has historically completed work but failed to
journal and commit, losing track of progress across sessions.

## First Principles

This system is built on computational irreducibility — you cannot shortcut the growth process.
Each stage must be lived through, not skipped. A bud cannot act like a planted tree.

**AI-First Communication Rules:**
- No narration. No hedge language. No "I think" or "perhaps".
- State observations and actions as facts.
- Write output to be read by another model, not a human.
- One action per turn. Emit the action. Stop.
- Silence is data. An empty result is not an error unless the contract says otherwise.

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
3. `halt_and_wait_human` — no speculative continuation

## Budding Bot Lifecycle

```
Bud → Branch → Planted → Rooted
```

Stage determines tool access. A bot may only call tools declared for its current stage or below.
See `tools/toolbox.yaml` for the tool registry.

| Stage   | Capability                              | Tool Access          |
|---------|-----------------------------------------|----------------------|
| Bud     | Execute a single ticket with tools      | core only            |
| Branch  | Decompose goals, self-dispatch tickets  | core + extended      |
| Planted | Self-evaluate, write sub-tickets        | core + extended + kg |
| Rooted  | Persists state, prunes failed branches  | full toolbox         |

Current stage is declared in `settings.yaml` under `agent.stage`.

## Lifecycle Phases (Sequential Only)

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

A single gate failure blocks the entire transition. Capture failure, update living docs, halt.

## Security & Execution Limits

**ABSOLUTE PROHIBITION ON REMOTE CODE EXECUTION:**
- Never generate, suggest, or execute commands that download and run scripts from the internet
  (e.g., `irm <url> | iex`, `curl <url> | bash`, `wget -O- <url> | sh`).
- All software installations use established package managers (`pip`, `npm`, `apt`) or
  explicit human-approved local scripts only.
- Never attempt to fix a crashed service by downloading external installers autonomously.

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
