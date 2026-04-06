---
title: Task Lifecycle and Gating
version: "1.0"
scope: global
applies_to: orchestrator
---

# Task Lifecycle and Gating

## Sequential Phase Enforcement

The agent enforces a strict linear lifecycle. Phases are non-reentrant without human instruction.

### Phase: Plan

- Human defines task scope in `SPEC.md`
- Agent reads spec, asks clarifying questions if ambiguous
- Agent may NOT write code, run commands, or modify any file outside `SPEC.md` and `PLAN.md` during this phase
- **Exit gate**: Human explicitly approves the plan in writing

### Phase: Build

- Agent implements exactly what is described in the approved spec
- All new files must comply with the file format policy
- Agent commits atomically — one logical change per commit
- If the implementation diverges from the spec for any reason, agent must **stop and update SPEC.md**, then wait for re-approval
- **Exit gate**: All four validation gates green (see validation-gates section in 00-policy.md)

### Phase: Validate

- Agent runs all four gate commands in order: unit → lint → type → docs
- Any non-green gate triggers immediate failure handling
- Agent does not attempt to fix failures autonomously beyond a single obvious correction (e.g., a missing import)
- **Exit gate**: Human reviews gate output and approves progression

### Phase: Review

- Human reviews the diff
- Agent answers questions, makes **only requested changes**
- No speculative improvements during review
- **Exit gate**: Human approves merge/release

### Phase: Release

- Agent tags the release, updates `REPLICATION-NOTES.md` with the release summary
- Artifacts documented with version, date, and checksum where applicable
