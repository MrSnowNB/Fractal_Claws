---
title: Failure Handling Procedure
version: "2.0"
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
- `response.choices` is empty after all retries exhausted

## Procedure (Ordered — Do Not Skip Steps)

### Step 1: Capture Logs

```python
# Save full stdout/stderr to logs/ directory
# Filename format: logs/ISS-<date>-<short-description>.log
```

All terminal output from the failing command must be saved verbatim. Do not truncate.

### Step 2: Update TROUBLESHOOTING.md

Append a new `TS-XXX` entry:
- Context, Symptom, Error Snippet, Probable Cause, Quick Fix, Permanent Fix, Prevention
- If the issue matches an existing entry, add a `recurrence` sub-field — no duplicates.

### Step 3: Update REPLICATION-NOTES.md

Append to the **Recurring Errors** table and, if the environment changed,
add a row to **Environment Deltas**.

### Step 4: Open ISSUE.md

Create a new `ISS-XXX` entry with:
- `status: open`
- `blocked_on: human`
- The exact requested human action spelled out clearly

### Step 5: halt_and_wait_human

Stop all work. Do not make further file changes, run commands, or attempt self-recovery.
Inform the human: "Halted on ISS-XXX. See ISSUE.md for required action."

## Prohibited Actions After Halt

- **No autonomous model switching:** If the LLM provider crashes or returns a connection error,
  do not modify `runtime.yaml`, `settings.yaml`, or any config to switch models.
- **No downloading fixes:** Never execute remote scripts to reinstall or fix a broken service.
- No retries without human instruction
- No speculative fixes
- No modifications to files outside living docs during halt state
- No advancing to the next lifecycle phase
