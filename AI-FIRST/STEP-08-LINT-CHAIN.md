# STEP-08 — Lint Hard-Fail + Multi-Ticket Dependency Chain

> **AI-FIRST DOC** — Canonical spec for Step 8. Read this before touching any file.
> Vendor-agnostic: no model names, no endpoint URLs.

---

## Goal

Promote `lint_ticket()` from warn-only to hard-fail in `ticket_io.py`, add a
multi-ticket dependency chain with `delegate_task`, add deadlock detection
across spawned children, and close the gate with a full-anchor journal entry.

---

## First Principles Rationale

The lint gate was purposely warn-not-block in Step 7 because the A3B child
running cold might succeed even with a lint violation. After real-run data,
we have the evidence to hard-fail with confidence.

Multi-ticket chaining is the next level of the parent↔child protocol —
Key-Brain fires a chain of dependent tickets and Fractal Claws manages
ordering and result propagation via the drain loop.

---

## Invariants This Step Preserves

1. `pytest tests/ -v` stays green after every sub-ticket.
2. `lint_ticket()` public API signature does not change (callers see the same call).
3. No raw `ticket.get()` / `ticket[key]` introduced in runner.py.
4. Journal entry for STEP-08-D uses the full anchor object (corrects STEP-07-F debt).

---

## Sub-Tickets (execute in order)

### STEP-08-A — Lint Hard-Fail Promotion

**File:** `src/ticket_io.py`  
**Test file:** `tests/test_ticket_io.py`  
**Depends on:** nothing (STEP-07 is complete)

#### What to build

In `lint_ticket()` inside `src/ticket_io.py`:

1. Add a `hard_fail: bool = False` parameter (backward-compatible default).
2. When `hard_fail=True`, raise `TicketIOError` instead of logging a warning
   for any violation that previously only warned.
3. In `load_ticket()`, pass `hard_fail=True` when the env var
   `FRACTAL_LINT_HARD_FAIL=1` is set. Default (env var absent) stays warn-only
   so existing tests and CI without the var are unaffected.
4. Log violations to `logs/lint-violations.jsonl` regardless of hard_fail mode
   (existing behaviour — do not remove).

#### Validation gate (STEP-08-A)

Add these tests to `tests/test_ticket_io.py`:

- `test_lint_hard_fail_raises_on_missing_task`  
  Create a ticket YAML missing the `task` field.  
  Call `lint_ticket(ticket, hard_fail=True)`.  
  Assert `TicketIOError` is raised.

- `test_lint_hard_fail_passes_clean_ticket`  
  Create a fully-valid ticket YAML.  
  Call `lint_ticket(ticket, hard_fail=True)`.  
  Assert no exception raised.

- `test_lint_warn_only_does_not_raise`  
  Create a ticket missing `task`.  
  Call `lint_ticket(ticket, hard_fail=False)` (default).  
  Assert no exception raised (warn-only mode unchanged).

- `test_load_ticket_hard_fail_env_var` (monkeypatch)  
  Monkeypatch `os.environ["FRACTAL_LINT_HARD_FAIL"] = "1"`.  
  Write a ticket YAML missing `task`.  
  Call `load_ticket(path)`.  
  Assert `TicketIOError` is raised.

All 4 new tests + all existing tests green.

---

### STEP-08-B — Multi-Ticket Dependency Chain

**Files:** `agent/runner.py`, `tools/delegate_task.py`  
**Test file:** `tests/test_runner_dispatch.py`  
**Depends on:** STEP-08-A

#### What to build

In `agent/runner.py`:

1. Extend `drain()` to support chains where a ticket's `produces` list is
   consumed by a child ticket's `consumes` list. This is already tracked in
   the Ticket dataclass — the drain loop must verify that all `consumes` items
   exist as files on disk (or as stdout: entries) before dispatching a ticket.
2. Add `_consumes_met(ticket: Ticket) -> bool` helper function that:
   - Returns `True` if `ticket.consumes` is empty.
   - For each entry in `ticket.consumes`: if it starts with `stdout:`, skip
     the disk check (stdout is ephemeral). Otherwise, assert the path exists.
   - Returns `False` if any required file is missing.
3. In the drain loop, gate dispatch behind `deps_met(ticket) AND _consumes_met(ticket)`.
   Log a clear message when `_consumes_met` blocks a ticket:
   `[runner] deferred TICKET-ID — missing consumes: [path1, path2]`

In `tools/delegate_task.py`:

1. When spawning a child ticket via `delegate_task`, propagate the `produces`
   list from the parent into the child's `context_files` so the child knows
   what it is expected to create.

#### Validation gate (STEP-08-B)

Add these tests to `tests/test_runner_dispatch.py`:

- `test_consumes_met_empty`  
  Build a Ticket with `consumes=[]`.  
  Assert `_consumes_met(ticket)` returns `True`.

- `test_consumes_met_file_present` (tmp_path)  
  Write a file to `tmp_path/output/foo.txt`.  
  Build a Ticket with `consumes=["output/foo.txt"]`.  
  Monkeypatch working directory or path check.  
  Assert `_consumes_met(ticket)` returns `True`.

- `test_consumes_met_file_missing`  
  Build a Ticket with `consumes=["output/missing.txt"]`.  
  Assert `_consumes_met(ticket)` returns `False`.

- `test_consumes_met_stdout_skipped`  
  Build a Ticket with `consumes=["stdout:fibonacci-10"]`.  
  Assert `_consumes_met(ticket)` returns `True` (stdout is ephemeral, skip).

All 4 new tests + all existing tests green.

---

### STEP-08-C — Deadlock Detection Across Spawned Children

**File:** `agent/runner.py`  
**Test file:** `tests/test_runner_dispatch.py`  
**Depends on:** STEP-08-B

#### What to build

In `agent/runner.py`, extend the blocked-ticket diagnostic in `drain()`:  

1. After the inner `if dispatched_this_pass == 0 and deferred:` block detects
   a stall, call a new helper `_detect_deadlock(deferred_paths: list) -> list`
   that returns a list of cycle groups (each group is a list of ticket IDs).
2. `_detect_deadlock` builds a `depends_on` graph from the deferred ticket set
   only, then runs a DFS cycle-detection. Any ticket whose dep chain forms a
   cycle within the deferred set is a deadlock participant.
3. Print a clear deadlock report:
   ```
   [runner] DEADLOCK detected — cycle group: [TASK-003, TASK-004]
   ```
4. Move deadlocked tickets to `tickets/failed/` with `status: escalated` and
   reason `deadlock` in the ticket's `_extras`.

#### Validation gate (STEP-08-C)

Add these tests to `tests/test_runner_dispatch.py`:

- `test_detect_deadlock_simple_cycle`  
  Build two in-memory Ticket objects: A depends_on=[B], B depends_on=[A].  
  Call `_detect_deadlock([path_A, path_B])` (mock load_ticket to return them).  
  Assert return value contains a cycle group with both IDs.

- `test_detect_deadlock_no_cycle`  
  Build two Tickets: A depends_on=[B], B depends_on=[].  
  Assert `_detect_deadlock([path_A, path_B])` returns `[]` (no cycles).

- `test_detect_deadlock_self_loop`  
  Build Ticket A with depends_on=[A] (self-loop).  
  Assert cycle group contains [A].

All 3 new tests + all existing tests green.

---

### STEP-08-D — Gate, Journal Entry, Commit, Push

**Files:** `logs/luffy-journal.jsonl`, `AI-FIRST/NEXT-STEPS.md`  
**Depends on:** STEP-08-C

#### What to do

1. Run `pytest tests/ -v`. All tests must be green (1 skipped permitted — the
   Windows-only `test_run_command_blocked_unix` skip is expected on Windows;
   the inverse on Ubuntu). Zero failures.

2. Append one journal entry to `logs/luffy-journal.jsonl`:

```json
{
  "ts": "<ISO-8601>",
  "step": "STEP-08-D",
  "action": "Gate green. Lint hard-fail promoted. Consumes chain guard added. Deadlock detection added.",
  "status": "done",
  "files": [
    "src/ticket_io.py",
    "agent/runner.py",
    "tools/delegate_task.py",
    "tests/test_ticket_io.py",
    "tests/test_runner_dispatch.py",
    "AI-FIRST/NEXT-STEPS.md"
  ],
  "anchor": {
    "system_state": "Lint gate hard-fails on FRACTAL_LINT_HARD_FAIL=1; drain loop guards consumes + deadlock; all tests green.",
    "open_invariants": [
      "lint_ticket() warn-only by default; hard-fail only when env var set",
      "_consumes_met() blocks dispatch until produces artifacts are on disk",
      "_detect_deadlock() moves cycle participants to tickets/failed/ with reason=deadlock"
    ],
    "next_entry_point": "STEP-09-A: read AI-FIRST/NEXT-STEPS.md Step 9 block; build tools/graphify.py AST walker first"
  }
}
```

3. Mark Step 8 `[x] DONE` in `AI-FIRST/NEXT-STEPS.md`.

4. `git add` all changed files + `logs/luffy-journal.jsonl`.
5. `git commit -m "STEP-08: lint hard-fail + consumes chain guard + deadlock detection"`
6. `git push`

---

## Validation Gate Summary

| Sub-ticket | Tests added | Must pass |
|---|---|---|
| STEP-08-A | 4 new tests in `test_ticket_io.py` | All existing + 4 new |
| STEP-08-B | 4 new tests in `test_runner_dispatch.py` | All existing + 4 new |
| STEP-08-C | 3 new tests in `test_runner_dispatch.py` | All existing + 7 new total |
| STEP-08-D | 0 (gate run only) | Full suite green |

Final gate command: `pytest tests/ -v`  
Expected: all passed, 1 skipped (platform-conditional), 0 failed.

---

## Files Touched in Step 8

| File | Change |
|---|---|
| `src/ticket_io.py` | Add `hard_fail` param to `lint_ticket()`; env-var wire in `load_ticket()` |
| `agent/runner.py` | Add `_consumes_met()` helper; gate dispatch; add `_detect_deadlock()`; move deadlocked tickets |
| `tools/delegate_task.py` | Propagate `produces` list into child `context_files` |
| `tests/test_ticket_io.py` | 4 new tests (lint hard-fail) |
| `tests/test_runner_dispatch.py` | 7 new tests (consumes chain + deadlock) |
| `logs/luffy-journal.jsonl` | 1 new entry with full anchor object |
| `AI-FIRST/NEXT-STEPS.md` | Mark Step 8 `[x] DONE` |
