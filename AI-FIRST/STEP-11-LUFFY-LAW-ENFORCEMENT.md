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
   cache hits are **logged as `LAW3_CACHE_HIT` journal events** with `law: 3` — clearly named
   to distinguish correct cache-conservation behavior from actual violations.
   (Renamed from `LAW_VIOLATION` for §3 to avoid misleading semantics: a cache hit is correct
   behavior, not an error.)

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
| 4 | Hook Law §3: emit `LAW3_CACHE_HIT` journal event when `CTX_BUDGET.should_read()` returns False (cache hit = correct behavior; event name reflects this) | `agent/runner.py` | unit |
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
  step09_roundtrip:
    description: "STEP-09 fix included in full suite — graph_scope/return_to round-trip"
    command: "pytest tests/test_ticket_io.py -v -k 'graph_scope or return_to'"
    pass_condition: "4 passed, 0 failed"
```

---

## Implementation Notes

### Law §3 Event Name — `LAW3_CACHE_HIT` (not `LAW_VIOLATION`)

A context budget cache hit is **correct behavior** — it means the file is already in context
and re-reading it would waste the token budget. Calling this a "violation" in the journal
creates misleading logs. The event name is `LAW3_CACHE_HIT` with `severity: "info"` to make
the semantics explicit:

```python
# In build_prompt() skip branch:
append_journal({
    "event": "LAW3_CACHE_HIT",
    "law": 3,
    "ticket": ticket_id or "drain",
    "path": cf,
    "reason": reason,
    "detail": "Context budget cache hit — file skipped (correct behavior, budget conserved)",
    "severity": "info",
})
```

This makes log scanning unambiguous: `LAW_VIOLATION` always means a real rule failure;
`LAW3_CACHE_HIT` means the system is working as intended.

### Law §2 Severity Model

§2 is a **hard block in normal `drain()` flow** and a **soft warning only when `--ticket` flag
bypasses `drain()`**. The check is:

```python
if bypassed_drain:
    print("  [law2] WARNING: scratchpad not read (--ticket bypass) — violation logged")
else:
    raise LawViolationError("Law §2 VIOLATION: SCRATCHPAD_READ not in session journal")
```

This eliminates the ambiguity in the original spec where §2 was universally soft.

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

**In `execute_ticket()`** after `SCRATCH_INIT` — hard block in normal flow, soft warning
only when `--ticket` bypass is active:

```python
# Law §2 check: scratchpad must have been read this session
session_scratchpad_read = _session_has_event("SCRATCHPAD_READ")
if not session_scratchpad_read:
    detail = "SCRATCHPAD_READ not found in session — drain() skipped Law §2 init"
    append_journal({
        "event": "LAW_VIOLATION", "law": 2, "ticket": ticket_id,
        "detail": detail,
    })
    if bypassed_drain:
        # --ticket flag skips drain() by design — soft warning only
        print(f"  [law2] WARNING: scratchpad not read (--ticket bypass) — violation logged")
    else:
        # Normal drain() path — hard block
        return _handle_failure(ticket, ip_path, detail)
```

Add helper `_session_has_event(event_name)` that reads `JOURNAL_PATH` and checks for the event
within the current `SESSION_UUID`.

### Task 4 — Law §3 cache hit logging

In `build_prompt()`, the skip branch emits `LAW3_CACHE_HIT` (not `LAW_VIOLATION`):

```python
else:
    summary = CTX_BUDGET.get_read_summary(cf) or f"[{reason}]"
    print(f"  [ctx] SKIP {cf} — {summary}")
    append_journal({
        "event": "LAW3_CACHE_HIT",
        "law": 3,
        "ticket": ticket_id if ticket_id else "drain",
        "path": cf,
        "reason": reason,
        "detail": "Context budget cache hit — file skipped (correct behavior, budget conserved)",
        "severity": "info",
    })
    prompt += f"\n\n--- {cf} {summary} ---"
```

---

## Constraints

- All output files: Markdown with YAML frontmatter or Python
- No files outside Scope may be created or modified
- `LawViolationError` must be importable from `agent.sequence_gate` in tests
- Law §1 enforcement is a **hard block** — ticket cannot close without scratch activity
- Law §2 enforcement is a **hard block in normal drain() flow**; soft warning only under `--ticket` bypass
- Law §3 enforcement is **informational only** — event name `LAW3_CACHE_HIT` makes this explicit
- On any failure: `troubleshoot` skill → halt for human input

---

## Definition of Done

The task is complete when:

- [ ] `agent/sequence_gate.py` exports `LawViolationError` and `assert_scratch_written()`
- [ ] `execute_ticket()` calls `assert_scratch_written()` before `TICKET_CLOSED` write
- [ ] `drain()` emits `SCRATCHPAD_READ` journal event at session start
- [ ] `execute_ticket()` checks for `SCRATCHPAD_READ` and raises `LawViolationError` in normal flow (soft warning only under `--ticket` bypass)
- [ ] `build_prompt()` emits `LAW3_CACHE_HIT` (severity: info) on every context cache hit
- [ ] `tests/test_luffy_law.py` has ≥6 passing tests covering §1 hard block, §2 hard/soft split, §3 info event
- [ ] `pytest tests/test_luffy_law.py -v` → 6 passed, 0 failed
- [ ] `pytest tests/ -v` → 0 failed (existing skips allowed)
- [ ] `pytest tests/test_ticket_io.py -v -k 'graph_scope or return_to'` → 4 passed (STEP-09 fix)
- [ ] `GATE-REPORT.md` shows ALL GREEN
- [ ] Journal entry written with full anchor object schema
- [ ] `git commit -m "STEP-11: Luffy Law mechanical enforcement"` and pushed

---

## Relationship to Other Steps

| Step | Relationship |
|---|---|
| STEP-08E (FIFO retention) | Must be complete — `prune_logs()` must exist before touching `execute_ticket()` |
| STEP-09 (Graphify) | Independent — STEP-11 does not touch `tools/graphify.py` |
| STEP-09 (ticket_io round-trip fix) | **Prerequisite for STEP-12** — `graph_scope`/`return_to` must round-trip losslessly before child_runner can dispatch tickets |
| STEP-10-D (context budget + sequence gate) | **Prerequisite** — `ContextBudget` and `SequenceGate` must be live |
| STEP-12-A (child_runner) | STEP-11 must be complete — Law §1 enforcement is a precondition for child spawning |

---

## Scratchpad (for Luffy — update before every action)

```
## Scratchpad
**Active ticket:** STEP-11
**Status:** spec updated — §2 severity finalized (hard in drain, soft under --ticket), LAW3_CACHE_HIT renamed, STEP-09 fix included in DoD
**Last action:** [2026-04-10] Spec pushed with §2 hard/soft split, LAW3_CACHE_HIT rename, STEP-09 round-trip gate
**Blockers:** none — STEP-10-D prerequisites are live, STEP-09 ticket_io fix is live
**Next:** Implement Task 1 — add LawViolationError + assert_scratch_written() to agent/sequence_gate.py
```
