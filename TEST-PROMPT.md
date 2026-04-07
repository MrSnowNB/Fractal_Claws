---
title: TEST-PROMPT.md — Fractal Claws POC End-to-End Test
version: "1.0"
---

# POC End-to-End Test

This is the canonical first test. It validates the full single-parent / single-child ticket loop on a multi-step problem that requires more than one tool call to complete.

The goal is deliberately simple enough to be debuggable but complex enough to require:
1. A `write_file` call (produce a script)
2. An `exec_python` call (run it)
3. A second `write_file` call (write the result)

If the model can do this in one ticket, the harness is proven.

---

## Test Prompt

Pass this string as the `--goal` argument to `runner.py`:

```
python agent/runner.py --goal "Write a Python script to output/fib.py that computes the first 10 Fibonacci numbers and prints them one per line. Execute the script. Write the printed output to output/fib_result.txt."
```

Or drop the ticket manually for a single `--once` run:

```yaml
# tickets/open/TASK-001.yaml
ticket_id: "TASK-001"
version: "1.1"
status: open
created_at: "2026-04-07T00:00:00"
updated_at: "2026-04-07T00:00:00"
task: >
  Write a Python script to output/fib.py that computes the first 10
  Fibonacci numbers and prints them one per line. Execute the script
  using exec_python. Write the printed output verbatim to
  output/fib_result.txt using write_file.
depends_on: []
context_files: []
result_path: "logs/TASK-001-result.txt"
attempts_log: "logs/TASK-001-attempts.jsonl"
timeout_seconds: 120
decrement: 3
depth: 0
max_tokens: null
allowed_tools:
  - write_file
  - exec_python
  - read_file
```

---

## Expected Tool Call Sequence

The model must emit tool blocks in this order with no gaps:

```
TOOL: write_file
PATH: output/fib.py
CONTENT:
<valid Python that prints 10 Fibonacci numbers>
END

TOOL: exec_python
PATH: output/fib.py
END

TOOL: write_file
PATH: output/fib_result.txt
CONTENT:
<stdout from exec_python pasted verbatim>
END
```

Any other order is a failure. Any missing block is a failure.

---

## Success Conditions

All of the following must be true for the ticket to count as PASS:

### 1. Filesystem
- [ ] `output/fib.py` exists and is non-empty
- [ ] `output/fib_result.txt` exists and is non-empty
- [ ] `logs/TASK-001-result.txt` exists and is non-empty
- [ ] `logs/TASK-001-attempts.jsonl` exists with at least one line
- [ ] `tickets/closed/TASK-001.yaml` exists (ticket moved from open)
- [ ] `tickets/open/TASK-001.yaml` does NOT exist

### 2. Output Correctness
- [ ] `output/fib_result.txt` contains exactly 10 lines
- [ ] Lines are: `0`, `1`, `1`, `2`, `3`, `5`, `8`, `13`, `21`, `34` (or `1,1,2...` variant — either sequence is acceptable)
- [ ] No tracebacks, no `ERROR:` strings in `output/fib_result.txt`

### 3. Runner Exit
- [ ] `runner.py` exits 0
- [ ] `[runner] all tickets closed — done` printed to stdout
- [ ] No `[runner] FAIL` line in stdout
- [ ] `finish_reason` in the JSONL record is `stop` (not `length`)

### 4. Audit Log
- [ ] `logs/TASK-001-attempts.jsonl` has a valid JSON object on line 1
- [ ] `outcome` field is `"pass"`
- [ ] `tokens` field is a positive integer
- [ ] `elapsed_s` field is a positive float

### 5. Validation Gates
- [ ] `pytest -q tests/` — 0 failures
- [ ] `ruff check src/` — clean

---

## Failure Modes to Watch For

| Symptom | Likely Cause |
|---|---|
| `finish_reason: length` in JSONL | Token budget too low — check `BUDGET_CEILING` in runner.py |
| No tool blocks parsed | Model returned prose instead of TOOL/PATH/END blocks |
| `exec_python` blocked | Script path not inside `output/` |
| `fib_result.txt` empty or missing | Model skipped the third write_file call |
| Ticket stays in `open/` | `deps_met()` failed or `execute_ticket()` raised before close |
| JSONL line missing | `_write_result()` not appending to attempts log |

---

## Verification Script

Run after the test to check all filesystem conditions automatically:

```bash
python -c "
import os, json, sys
errors = []

for f in ['output/fib.py', 'output/fib_result.txt',
          'logs/TASK-001-result.txt', 'logs/TASK-001-attempts.jsonl',
          'tickets/closed/TASK-001.yaml']:
    if not os.path.exists(f):
        errors.append(f'MISSING: {f}')

if os.path.exists('tickets/open/TASK-001.yaml'):
    errors.append('FAIL: ticket still in open/')

if os.path.exists('output/fib_result.txt'):
    lines = open('output/fib_result.txt').read().strip().splitlines()
    if len(lines) != 10:
        errors.append(f'FAIL: fib_result.txt has {len(lines)} lines, expected 10')

if os.path.exists('logs/TASK-001-attempts.jsonl'):
    line = open('logs/TASK-001-attempts.jsonl').readline().strip()
    try:
        rec = json.loads(line)
        if rec.get('outcome') != 'pass':
            errors.append(f'FAIL: outcome={rec.get(\"outcome\")}')
        if rec.get('finish') == 'length':
            errors.append('FAIL: finish_reason=length (token budget hit)')
    except Exception as e:
        errors.append(f'FAIL: invalid JSONL: {e}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
else:
    print('ALL CHECKS PASS')
"
```

---

## What This Proves

A clean pass on this test proves:
- The model can generate a multi-step tool call sequence from a single ticket
- `write_file` → `exec_python` → `write_file` chain works end-to-end
- The token budget is sufficient for a real task (not just a ping)
- The JSONL audit log is being written correctly
- The ticket state machine completes the full `open → closed` transition
- The harness is ready for decomposed multi-ticket runs via `--goal`
