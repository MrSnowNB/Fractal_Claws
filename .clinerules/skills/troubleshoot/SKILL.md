---
name: troubleshoot
description: >
  Debug a failure, error, exception, or unexpected behavior. Use when something
  broke, a command failed, a test is erroring, an OOM occurred, a port conflict
  appeared, a dependency failed to resolve, or the agent needs to halt and document
  an issue before waiting for human input.
version: "1.0"
last_updated: "2026-04-01"
---

# troubleshoot

## Purpose

Capture, classify, and document any failure encountered during any lifecycle phase.
This skill produces a complete `TROUBLESHOOTING.md` entry and a new `ISSUE.md` record,
then halts for human input. It does not attempt autonomous fixes beyond the Quick Fix
defined in a matching seeded entry.

## Instructions

Work through each step in order. Do not skip steps.

---

### Step 1 — Capture Full Output

Save the complete terminal output (stdout + stderr) verbatim:

```powershell
# Redirect both streams to a timestamped log
<failing-command> 2>&1 | Tee-Object -FilePath "logs\ISS-<date>-<short-slug>.log"
```

If the failure already occurred and output was not captured, re-run the failing
command once with the above redirect before proceeding.

**Log filename format**: `logs\ISS-YYYY-MM-DD-<slug>.log`
Example: `logs\ISS-2026-04-01-pytest-import-error.log`

---

### Step 2 — Match Against Seeded Entries

Check `TROUBLESHOOTING.md` for an existing entry matching this failure pattern.

**Seeded patterns to check first:**

| TS ID | Pattern Keywords | Quick Fix Summary |
|-------|-----------------|-------------------|
| TS-001 | `ResolutionImpossible`, `dependency conflict`, pip loop | Add `constraints.txt`, pin indirect deps |
| TS-002 | `CUDA out of memory`, `HIP error: out of memory`, OOM | Reduce batch, set `torch_dtype=torch.float16` |
| TS-003 | `Address already in use`, `WinError 10048`, port conflict | Randomized port bind with `get_free_port()` |

If a match is found:
- Apply the **Quick Fix** from that entry
- Add a `recurrence` field to the existing entry (do not duplicate)
- Skip to Step 5

If no match is found:
- Proceed to Step 3 to create a new entry

---

### Step 3 — Create New TROUBLESHOOTING.md Entry

Append to `TROUBLESHOOTING.md` using this exact format:

```markdown
---
id: TS-<next sequential number>
date: "<YYYY-MM-DD>"
phase: <Plan|Build|Validate|Review|Release>
---

**Context**: <What was the agent doing when this occurred?>
**Symptom**: <What observable behavior indicated a problem?>
**Error Snippet**:
```
<paste exact error — first 20 lines maximum>
```
**Probable Cause**: <Why did this likely occur?>
**Quick Fix**: <Immediate workaround — one or two commands maximum>
**Permanent Fix**: <Root-cause resolution to implement later>
**Prevention**: <Rule, test, or check that prevents recurrence>
```

Rules for filling in entries:
- **Error Snippet**: Never truncate silently — if longer than 20 lines, note `(truncated — full output in logs/ISS-XXX.log)`
- **Probable Cause**: Be specific. "Unknown error" is not acceptable — make a reasoned hypothesis
- **Quick Fix**: Must be actionable in under 2 minutes. If no quick fix exists, write `None — requires human investigation`
- **Permanent Fix**: If unknown, write `TBD — pending human review`
- **Prevention**: At minimum, reference the gate or rule that would have caught this

---

### Step 4 — Update REPLICATION-NOTES.md

Append a row to the **Recurring Errors** table:

```markdown
| TS-XXX | <one-line error description> | <Quick Fix summary> | First occurrence |
```

If the error involves an environment change (new package, hardware config, model version):
also append a row to the **Environment Deltas** table.

---

### Step 5 — Open ISSUE.md Entry

Append a new issue block to `ISSUE.md`:

```markdown
---
issue_id: "ISS-<next sequential number>"
date_opened: "<YYYY-MM-DD>"
phase: "<current phase>"
status: "open"
related_ts: "<TS-XXX or none>"
blocked_on: "human"
---

**Summary**: <One sentence — what failed>
**Context**: <What the agent was attempting when it failed>
**Logs**: `logs\ISS-<date>-<slug>.log`
**Requested Human Action**: <Exactly what decision or action is needed — be specific>
```

**Requested Human Action** must be a concrete question or instruction. Examples:
- "Please confirm whether to pin `tokenizers==0.15.2` in constraints.txt and re-run pip install."
- "GPU OOM on batch_size=4 — please advise: reduce to 2, or switch to CPU offload?"
- "Port 8100 is in use — please kill the conflicting process or approve a new port range."

Vague requests like "please investigate" are not acceptable.

---

### Step 6 — Halt

Report to the human exactly:

```
Halted on ISS-<number>. <One sentence summary of failure>.
See ISSUE.md for required action and logs/<logfile> for full output.
```

**Stop all work.** Do not run further commands, modify files outside the living docs,
attempt speculative fixes, or advance the lifecycle phase.

---

## Known Pitfalls (ClawBot-Specific)

These are recurring failure modes specific to this hardware and model stack.
Check these before writing a new TS entry — they may already be documented.

**Qwen3-Coder-Next context overflow**
- Symptom: Responses truncate mid-sentence or tool calls reference files not in context
- Probable cause: `<think>` blocks enabled during Build phase exhausted the 128K window
- Quick fix: Start a new Cline session; use `/no_think` for all Build-phase prompts
- Prevention: `04-qwen-coder.md` rule — suppress thinking in Build/Act phases

**Lemonade model eviction**
- Symptom: Sub-agent calls suddenly slow (30-90s latency spike) mid-session
- Probable cause: Lemonade started without `--max-loaded-models 2`; LFM2.5 was evicted
- Quick fix: Restart Lemonade with `lemonade-server serve --max-loaded-models 2`
- Prevention: Document Lemonade start command in `REPLICATION-NOTES.md` setup checklist

**ROCm/HIP driver mismatch after Windows Update**
- Symptom: `HIP error: invalid device function` or model fails to load after reboot
- Probable cause: Windows Update replaced AMD driver; ROCm runtime version mismatch
- Quick fix: Roll back AMD driver in Device Manager to previous version
- Prevention: Pause Windows Update during active ClawBot development sessions

---

## Output Format

- `TROUBLESHOOTING.md` entry: Markdown with YAML frontmatter block
- `ISSUE.md` entry: Markdown with YAML frontmatter block
- `REPLICATION-NOTES.md` row: Markdown table row appended in place
- Log files: Plain text, no frontmatter required
