---
name: spec-writer
description: >
  Write a task specification, create SPEC.md, plan a new task, decompose a feature
  into atomic steps, or define the scope before any Build phase begins. Use when
  starting any new task, feature, fix, or agent capability that requires human
  approval before implementation.
version: "1.0"
last_updated: "2026-04-01"
---

# spec-writer

## Purpose

Produce a complete `SPEC.md` for any task before a single line of code or file
is written. The spec is the contract between the human and the agent. No Build
phase may begin without a human-approved spec.

A good spec makes the validation gates trivially definable — if you cannot write
the pass condition for a gate, the task is not yet well-defined.

---

## Instructions

Work through each step in order. Stop at Step 3 and wait for human approval
before proceeding to Step 4.

---

### Step 1 — Clarify Before Writing

Before drafting the spec, ask the minimum necessary clarifying questions.
Maximum three questions. Do not ask about implementation details — only scope
and acceptance criteria.

Mandatory questions if not already answered:
1. What is the single observable outcome that means this task is done?
2. What files or systems are in scope? (Everything else is explicitly out of scope)
3. Are there any constraints — performance, format, compatibility, or policy?

If the human's request already answers all three, skip to Step 2.

---

### Step 2 — Draft SPEC.md

Write `SPEC.md` to the project root using this exact template:

```markdown
---
title: "<task name — imperative verb phrase>"
spec_id: "SPEC-<YYYY-MM-DD>-<slug>"
status: "draft"
phase: "Plan"
created: "<YYYY-MM-DD>"
author: "Qwen3-Coder-Next (orchestrator)"
approved_by: "pending"
---

# <Task Name>

## Objective

<One paragraph. What problem does this solve? What is the concrete deliverable?>

## Scope

### In Scope
- <File or system 1>
- <File or system 2>

### Out of Scope
- <Explicitly excluded item 1>
- <Explicitly excluded item 2>
- Any file not listed above

## Atomic Tasks

Each task is independently testable and produces one verifiable output.

| # | Task | Output | Gate |
|---|------|--------|------|
| 1 | <verb phrase> | <file or artifact> | unit / lint / type / drift |
| 2 | <verb phrase> | <file or artifact> | unit / lint / type / drift |

## Validation Gates

Define the exact pass condition for each gate this task touches:

```yaml
gates:
  unit:
    command: "pytest -q <test file or pattern>"
    pass_condition: "<exact expected output>"
  lint:
    command: "ruff check <path>"
    pass_condition: "clean"
  type:
    command: "mypy <path>"
    pass_condition: "0 errors"
  docs:
    description: "<what drift check verifies for this task>"
    pass_condition: "all modified files listed in Scope above"
```

## Constraints

- All output files: Markdown with YAML frontmatter or pure YAML
- No files outside Scope may be created or modified
- Sub-agent tasks (if any): delegated via `sub-agent-task` skill
- On any failure: `troubleshoot` skill → halt for human input

## Definition of Done

The task is complete when:
- [ ] All atomic tasks in the table above are finished
- [ ] All validation gates are green
- [ ] `GATE-REPORT.md` shows ALL GREEN
- [ ] Human has approved the diff in Review phase
```

---

### Step 3 — Present and Halt for Approval

After writing `SPEC.md`, present a summary to the human:

```
SPEC.md written. Waiting for approval before Build phase begins.

Summary:
- Spec ID: SPEC-<id>
- Tasks: <N> atomic tasks
- Gates: <list which gates apply>
- In scope: <file list>
- Out of scope: everything else

Please reply APPROVED to begin Build, or provide revision instructions.
```

**Do not write any code, create any implementation files, or run any commands
until the human replies APPROVED.**

---

### Step 4 — On Approval

When human approves:

1. Update `SPEC.md` frontmatter:
   ```yaml
   status: "approved"
   approved_by: "human"
   approved_date: "<YYYY-MM-DD>"
   ```

2. Create `PLAN.md` — a sequenced execution plan derived from the atomic tasks table:

```markdown
---
title: "Execution Plan: <task name>"
spec_id: "<SPEC-id>"
status: "active"
phase: "Build"
created: "<YYYY-MM-DD>"
---

# Execution Plan

## Task Sequence

| Step | Action | Sub-agent? | Gate |
|------|--------|------------|------|
| 1 | <action> | yes / no | <gate> |
| 2 | <action> | yes / no | <gate> |

## Sub-Agent Tasks

<List any tasks delegated to LFM2.5 with their task spec summaries>

## Checkpoints

- After step <N>: run `validate-gates` skill
- At 60% context: write CHECKPOINT.md, alert human
```

3. Transition to Build phase. Begin with Task 1 from the atomic tasks table.

---

## Spec Quality Rules

A spec is not approvable if any of these are true:

- **Vague objective** — "improve the system" or "make it better" — must be a concrete deliverable
- **Missing out-of-scope list** — if you don't say what's excluded, everything is implicitly in scope
- **Gate pass conditions undefined** — every gate must have an exact expected output, not "should pass"
- **Tasks not atomic** — a task that produces two different outputs is two tasks
- **No Definition of Done** — the checkbox list must exist and be binary

If the human's request cannot produce a valid spec by these rules, ask for clarification
before drafting. Do not write an invalid spec and ask for approval on it.

---

## Output Format

- `SPEC.md`: Markdown with YAML frontmatter — project root
- `PLAN.md`: Markdown with YAML frontmatter — project root
- Both files are append-never, replace-on-revision
- Previous spec versions: rename to `SPEC-<id>-v<n>.md` before overwriting
