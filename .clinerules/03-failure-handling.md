---
title: Failure Handling Procedure
version: "1.0"
scope: global
applies_to: all_agents
---

# Failure Handling Procedure

## When to Trigger

Trigger the full failure procedure on **any** of:
- A validation gate returns non-green output
- An unhandled exception occurs during task execution
- The agent is uncertain about the correct next action
- A file format violation is detected
- A phase transition condition is not met

## Procedure (Ordered — Do Not Skip Steps)

### Step 1: Capture Logs

```python
# Save full stdout/stderr to logs/ directory
# Filename format: logs/ISS-<date>-<short-description>.log
```

All terminal output from the failing command must be saved verbatim. Do not truncate.

### Step 2: Update TROUBLESHOOTING.md

Append a new `TS-XXX` entry using the standard format:
- Context, Symptom, Error Snippet, Probable Cause, Quick Fix, Permanent Fix, Prevention
- If the issue matches an existing seeded entry, add a `recurrence` sub-field to that entry instead of creating a duplicate

### Step 3: Update REPLICATION-NOTES.md

Append to the **Recurring Errors** table and, if the environment changed, add a row to **Environment Deltas**.

### Step 4: Open ISSUE.md

Create a new `ISS-XXX` entry with:
- `status: open`
- `blocked_on: human`
- The exact requested human action spelled out clearly

### Step 5: halt_and_wait_human

Stop all work. Do not make further file changes, run commands, or attempt self-recovery.
Inform the human: "Halted on ISS-XXX. See ISSUE.md for required action."

## Prohibited Actions After Halt

- No retries without human instruction
- No speculative fixes ("I'll try changing X to see if it helps")
- No modifications to files outside the living docs during halt state
- No advancing to the next lifecycle phase
