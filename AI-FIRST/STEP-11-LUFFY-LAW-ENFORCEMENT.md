---
title: "Enforce Luffy Laws Mechanically in runner.py"
spec_id: "SPEC-2026-04-10-luffy-law-enforcement"
status: "approved"
phase: "Build"
created: "2026-04-10"
author: "Perplexity (orchestrator assist)"
approved_by: "human"
approved_date: "2026-04-10"
---

# STEP-11: Luffy Law Mechanical Enforcement

## Background

The three Luffy Laws exist in `.clinerules/00-policy.md` and `AI-FIRST/NEXT-STEPS.md` as **prose
policy** — Luffy reads them at session start and is expected to comply. History shows this is
insufficient:

- STEP-10-D: `GRAPHIFY_COMPLETE` was never written to the journal
- STEP-10-B / STEP-10-C tickets were not closed before the session ended
- Law §2 (scratchpad-first read) has zero code enforcement — only a doc note

The root cause: **none of the three laws block execution when violated**. They are warnings at
best. This step converts all three from documentation into mechanical gates.

---

## Objective

Wire three code-level enforcement points into `agent/runner.py` so that:

1. **Law §1** — `execute_ticket()` cannot reach `TICKET_CLOSED` unless a `SCRATCH` journal entry
   exists for the current ticket in the current session.
2. **Law §2** — `drain()` writes a `SCRATCHPAD_READ` journal event at session start (after reading
   `AI-FIRST/NEXT-STEPS.md` scratchpad section) and `execute_ticket()` checks for it before
   proceeding past `SCRATCH_INIT`.
3. **Law §3** — `build_prompt()` already calls `CTX_BUDGET.should_read()`. This step ensures
   violations (reading a cached file anyway) are **logged as `LAW_VIOLATION` journal events**
   with `law: 3` rather than silently skipped.

---

## Scope

### In Scope

- `agent/runner.py` — three enforcement hooks added
- `agent/sequence_gate.py` — add `assert_scratch_written(ticket_id)` helper
- `tests/test_luffy_law.py` (new) — unit tests for all three enforcement points
- `AI-FIRST/NEXT-STEPS.md` — scratchpad section updated to reflect STEP-11 status

### Out of Scope

- `agent/context_budget.py` — no changes; `should_read()` already exists
- `agent/child_runner.py` — not yet implemented; STEP-12 concern
- Any ticket file, skill YAML, or spec outside this list
- `.clinerules/` — policy docs are authoritative; this step only adds code enforcement

---

## Atomic Tasks

| # | Task | Output | Gate |
|---|------|--------|------|
| 1 | Add `assert_scratch_written(ticket_id)` to `SequenceGate` | `agent/sequence_gate.py` | unit |
| 2 | Hook Law §1: call `SEQ_GATE.assert_scratch_written(ticket_id)` in `execute_ticket()` before writing `TICKET_CLOSED` | `agent/runner.py` | unit |
| 3 | Hook Law §2: emit `SCRATCHPAD_READ` journal event in `drain()` session start block; check for it in `execute_ticket()` after `SCRATCH_INIT` | `agent/runner.py` | unit |
| 4 | Hook Law §3: emit `LAW_VIOLATION` journal event when `CTX_BUDGET.should_read()` returns False but a read is attempted anyway (detect via `mark_read` on a cached path) | `agent/runner.py` | unit |
| 5 | Write `tests/test_luffy_law.py` covering all three laws (6 tests minimum) | `tests/test_luffy_law.py` | unit |
| 6 | Run full suite, write journal entry with anchor, commit, push | journal + git | full suite |

---

## Validation Gates

```yaml
gates:
  unit:
    command: "pytest tests/test_luffy_law.py -v"
    pass_condition: "6 passed, 0 failed, 0 errors"
  full_suite:
    command: "pytest tests/ -v"
    pass_condition: "0 failed (existing skips allowed)"
  lint:
    command: "ruff check agent/runner.py agent/sequence_gate.py tests/test_luffy_law.py"
    pass_condition: "clean output"
  type:
    command: "mypy agent/runner.py agent/sequence_gate.py"
    pass_condition: "0 errors"
  docs:
    description: "NEXT-STEPS.md scratchpad section updated; STEP-11 marked in build queue"
    pass_condition: "STEP-11 row present in build queue with gate status"
```

---

## Implementation Notes

### Task 1 — `SequenceGate.assert_scratch_written(ticket_id)`

The scratch file lives at `logs/scratch-{ticket_id}.jsonl`. A session is considered to have
written scratch if **any event with `event != SCRATCH_INIT`** exists for this ticket in the
current session UUID (already embedded in every `scratch_append` call via `session` field from
`runner.py`'s `SESSION_UUID`).

```python
def assert_scratch_written(self, ticket_id: str) -> None:
    """
    Law §1: raise LawViolationError if no non-INIT scratch event exists
    for ticket_id in the current session.
    """
    scratch_path = Path(self.journal_path).parent / f"scratch-{ticket_id}.jsonl"
    if not scratch_path.exists():
        raise LawViolationError(f"Law §1 VIOLATION: scratch file missing for {ticket_id}")
    events = []
    with open(scratch_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    non_init = [e for e in events if e.get("event") not in ("SCRATCH_INIT", "SCRATCH_CLOSE")]
    if not non_init:
        raise LawViolationError(
            f"Law §1 VIOLATION: scratch for {ticket_id} has no non-INIT events — "
            f"Luffy did not write to scratchpad during execution"
        )
```

Add `LawViolationError` as a new exception class in `sequence_gate.py`.

### Task 2 — Law §1 hook in `execute_ticket()`

Insert immediately before the `TICKET_CLOSED` journal write in the `if passed:` block:

```python
# Law §1 enforcement
try:
    SEQ_GATE.assert_scratch_written(ticket_id)
except LawViolationError as e:
    append_journal({
        "event": "LAW_VIOLATION", "law": 1, "ticket": ticket_id,
        "detail": str(e),
    })
    return _handle_failure(ticket, ip_path, str(e))
```

This means a ticket that passes gate_command but has no scratch activity is still treated as a
failure, not a close. The failure message in ISSUE.md will say `Law §1 VIOLATION`.

### Task 3 — Law §2 hook

**In `drain()` session start block** (after `SESSION_START` journal write):

```python
# Law §2: read scratchpad, emit journal event
scratchpad_path = "AI-FIRST/NEXT-STEPS.md"
should, _ = CTX_BUDGET.should_read(scratchpad_path, zone="system_prompt")
if should:
    scratchpad_content = tool_read_file(scratchpad_path)
    CTX_BUDGET.mark_read(scratchpad_path, zone="system_prompt")
    append_journal({
        "event": "SCRATCHPAD_READ",
        "path": scratchpad_path,
        "law": 2,
        "cached": False,
    })
else:
    append_journal({
        "event": "SCRATCHPAD_READ",
        "path": scratchpad_path,
        "law": 2,
        "cached": True,
        "note": "CTX cache hit — scratchpad unchanged since last read",
    })
```

**In `execute_ticket()`** after `SCRATCH_INIT`, check that `SCRATCHPAD_READ` exists in the
current session's journal before proceeding:

```python
# Law §2 check: scratchpad must have been read this session
session_scratchpad_read = _session_has_event("SCRATCHPAD_READ")
if not session_scratchpad_read:
    append_journal({
        "event": "LAW_VIOLATION", "law": 2, "ticket": ticket_id,
        "detail": "SCRATCHPAD_READ not found in session — drain() skipped Law §2 init",
    })
    # Non-fatal: emit warning but do not block (drain may have been bypassed by --ticket flag)
    print(f"  [law2] WARNING: scratchpad not read this session — violation logged")
```

Add helper `_session_has_event(event_name)` that reads `JOURNAL_PATH` and checks for the event
within the current `SESSION_UUID`.

### Task 4 — Law §3 violation logging

In `build_prompt()`, the existing pattern is:

```python
should, reason = CTX_BUDGET.should_read(cf, zone="ticket_context")
if should:
    content = tool_read_file(cf)
    CTX_BUDGET.mark_read(cf, zone="ticket_context")
    ...
else:
    print(f"  [ctx] SKIP {cf} — {reason}")
    prompt += f"\\n\\n--- {cf} {summary} ---"
```

The skip branch is already correct. Law §3 violation only occurs if code reads a file despite
`should_read()` returning False. To detect this, wrap the skip branch with a journal event:

```python
else:
    summary = CTX_BUDGET.get_read_summary(cf) or f"[{reason}]"
    print(f"  [ctx] SKIP {cf} — {summary}")
    append_journal({
        "event": "LAW_VIOLATION", "law": 3, "ticket": ticket_id if ticket_id else "drain",
        "path": cf, "reason": reason,
        "detail": "Context budget cache hit — file skipped per Law §3",
        "severity": "info",  # info, not error — skip is correct behaviour
    })
    prompt += f"\\n\\n--- {cf} {summary} ---"
```

Note: Law §3 "violation" here is **informational** — it records *when* the law saved a context
read. A true violation (reading anyway) would require bypassing `should_read()`, which the current
code never does. The journal entry provides an audit trail of cache hits for tuning.

---

## Constraints

- All output files: Markdown with YAML frontmatter or Python
- No files outside Scope may be created or modified
- `LawViolationError` must be importable from `agent.sequence_gate` in tests
- Law §1 enforcement is a **hard block** — ticket cannot close without scratch activity
- Law §2 enforcement is a **soft warning** — `--ticket` flag bypasses `drain()` so §2 cannot
  always be guaranteed; log but do not fail
- Law §3 enforcement is **informational only** — records cache hits, not actual violations
- On any failure: `troubleshoot` skill → halt for human input

---

## Definition of Done

The task is complete when:

- [ ] `agent/sequence_gate.py` exports `LawViolationError` and `assert_scratch_written()`
- [ ] `execute_ticket()` calls `assert_scratch_written()` before `TICKET_CLOSED` write
- [ ] `drain()` emits `SCRATCHPAD_READ` journal event at session start
- [ ] `execute_ticket()` checks for `SCRATCHPAD_READ` and logs `LAW_VIOLATION` if absent
- [ ] `build_prompt()` emits `LAW_VIOLATION` (severity: info) on every context cache hit
- [ ] `tests/test_luffy_law.py` has ≥6 passing tests covering §1 hard block, §2 warning, §3 info
- [ ] `pytest tests/test_luffy_law.py -v` → 6 passed, 0 failed
- [ ] `pytest tests/ -v` → 0 failed (existing skips allowed)
- [ ] `GATE-REPORT.md` shows ALL GREEN
- [ ] Journal entry written with full anchor object schema
- [ ] `git commit -m "STEP-11: Luffy Law mechanical enforcement"` and pushed

---

## Relationship to Other Steps

| Step | Relationship |
|---|---|
| STEP-08E (FIFO retention) | Must be complete — `prune_logs()` must exist before touching `execute_ticket()` |
| STEP-09 (Graphify) | Independent — STEP-11 does not touch `tools/graphify.py` |
| STEP-10-D (context budget + sequence gate) | **Prerequisite** — `ContextBudget` and `SequenceGate` must be live |
| STEP-12 (child_runner) | STEP-11 must be complete — Law §1 enforcement is a precondition for child spawning |

---

## Scratchpad (for Luffy — update before every action)

```
## Scratchpad
**Active ticket:** STEP-11
**Status:** spec written — awaiting Build phase
**Last action:** [09:42] Spec pushed to AI-FIRST/STEP-11-LUFFY-LAW-ENFORCEMENT.md
**Blockers:** none — STEP-10-D prerequisites are live
**Next:** Implement Task 1 — add LawViolationError + assert_scratch_written() to agent/sequence_gate.py
```
