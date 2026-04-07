# Step 1 — Typed Ticket I/O Bridge (`src/ticket_io.py`)

> **AI-FIRST DOC** — This file is the authoritative specification for Step 1.
> It is written for coding agents (Cline, Hermes, OpenClaw) and human engineers equally.
> Every claim here maps 1-to-1 to a test in `tests/test_ticket_io.py`.
> **Vendor-agnostic:** no model names, no endpoint URLs, no hardware assumptions.

---

## Purpose

`src/ticket_io.py` is the typed I/O boundary between the raw YAML files on disk
and the canonical `Ticket` dataclass defined in `src/operator_v7.py`.

Before this module existed, `agent/runner.py` loaded tickets as plain Python
`dict` objects and accessed fields with `.get("field")`. This made schema
violations silent — a missing `ticket_id` or a misspelled `status` value
would propagate silently through the drain loop and produce confusing failures.

This module fixes that by:
1. **Validating** required fields at load time (raises `TicketIOError` on failure)
2. **Coercing** enum fields (`status`, `priority`) with aliases for backward compat
3. **Preserving** runner-specific extras (`task`, `depends_on`, `tags`, etc.) in a
   `_extras` passthrough dict so round-trips are lossless
4. **Providing** a `as_dict()` shim so `runner.py` can migrate call-sites one at a time

---

## File Location

```
src/ticket_io.py
```

---

## Public API

### `load_ticket(path: str) -> Ticket`

Loads a YAML ticket file and returns a validated `Ticket` dataclass.

- Handles **two-document YAML** (legacy format: doc[0] base + doc[1] overlay merged)
- Applies `_DEFAULTS` for any absent optional fields
- Coerces `status` and `priority` to enums via `_coerce_status()` / `_coerce_priority()`
- Attaches runner extras as `ticket._extras` (non-dataclass attribute)
- **Raises** `TicketIOError` if file missing, YAML invalid, or `ticket_id` absent

### `save_ticket(path: str, ticket: Ticket | dict) -> None`

Writes a ticket to YAML. Accepts both `Ticket` dataclass and raw `dict`.

- `Ticket` → `to_dict()` + re-inject `_extras` + status alias (`pending` → `open`)
- `dict` → written as-is (backward compat)
- Always stamps `updated_at` on save

### `as_dict(ticket: Ticket | dict) -> dict`

Returns a flat `dict` regardless of input type. Use during incremental migration
of `runner.py` call-sites that still use `.get("field")` syntax.

### `move_ticket(src: str, dst_dir: str) -> str`

Atomically moves a ticket YAML to a destination directory.
Returns the new full path. Raises `TicketIOError` if source missing.

### `scan_dir(directory: str) -> list[Ticket]`

Loads all `*.yaml` files in a directory as `Ticket` objects, sorted by filename.
Corrupt/invalid files are logged and skipped (never raised).

### `ticket_exists(ticket_id: str, directory: str) -> bool`

Returns `True` if `<directory>/<ticket_id>.yaml` exists on disk.

---

## Status Alias Map

runner.py writes these values to YAML. ticket_io maps them to canonical enums:

| On-disk value | TicketStatus enum |
|---|---|
| `open` | `PENDING` |
| `pending` | `PENDING` |
| `closed` | `CLOSED` |
| `escalated` | `ESCALATED` |
| `failed` | `ESCALATED` |
| *(unknown)* | `PENDING` + warning log |

---

## Ticket YAML Format (Canonical)

A valid ticket must have at minimum:

```yaml
ticket_id: TASK-001
task: "Description of the work to be done."
```

Full example with all optional fields:

```yaml
ticket_id: TASK-001
title: "Example ticket"
task: >
  Write a Python script to output/hello.py that prints 'hello world'.
  Execute it. Verify stdout contains 'hello world'.
rationale: Demonstrates the ticket contract.
produces: [output/hello.py, stdout:hello-world]
consumes: []
tags: [example, write-and-exec]
depends_on: []
allowed_tools: [write_file, exec_python]
agent: ""
status: open
depth: 0
max_depth: 2
decrement: 3
priority: medium
result_path: logs/TASK-001-result.txt
context_files: []
```

---

## Error Hierarchy

```
TicketIOError(Exception)
    Raised on: file missing, YAML parse failure, missing required fields
    Callers should: catch and fail-fast (ticket is unrunnable)

ValidationWarning(UserWarning)
    Issued on: unknown enum values coerced to defaults
    Callers should: log and continue
```

---

## Migration Path for `runner.py`

This module does NOT require immediate changes to `runner.py`.
Migration is incremental across three phases:

### Phase A — Drop-in replacement (zero breakage)
```python
from src.ticket_io import load_ticket, as_dict
ticket = as_dict(load_ticket(ticket_path))  # still a dict
```

### Phase B — Incremental attribute access
```python
ticket = load_ticket(ticket_path)
ticket_id = ticket.id                           # was: ticket.get("ticket_id")
deps      = ticket._extras.get("depends_on", []) # was: ticket.get("depends_on") or []
```

### Phase C — Full typed access, drop `as_dict()`
```python
ticket = load_ticket(ticket_path)
# All fields via ticket.field or ticket._extras["field"]
```

---

## Validation Gate

The automated test gate for this step lives at:

```
tests/test_ticket_io.py
```

Run it with:

```bash
python -m pytest tests/test_ticket_io.py -v
```

**All tests must pass (0 failures, 0 errors) before Step 2 begins.**

The gate is designed to be run by the coding agent in the harness as a
ticket action:

```yaml
tool: exec_python
path: output/run_gate_step1.py
```

where `output/run_gate_step1.py` contains:

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_ticket_io.py", "-v", "--tb=short"],
    capture_output=True, text=True
)
print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
```

---

## Reproducibility Checklist

Any agent or engineer cloning this repo on any machine with Python 3.10+
and `pyyaml` installed should be able to:

- [ ] `python -m pytest tests/test_ticket_io.py -v` → all green
- [ ] No model, endpoint, or API key required for these tests
- [ ] No network access required
- [ ] Tests are fully deterministic (no random, no time-dependent logic)
- [ ] Tests clean up all temp files via `tmp_path` fixtures

---

## Dependencies

| Package | Used for | Install |
|---|---|---|
| `pyyaml` | YAML read/write | `pip install pyyaml` |
| `pytest` | Test runner | `pip install pytest` |

No other external dependencies. `src/operator_v7.py` is internal.

---

## Step Completion Criteria

Step 1 is **complete** when:

1. `src/ticket_io.py` exists and imports cleanly
2. `tests/test_ticket_io.py` passes with 0 failures
3. This document exists at `AI-FIRST/STEP-01-TICKET-IO.md`
4. `AI-FIRST/NEXT-STEPS.md` shows Step 1 as `[x] DONE`

Step 2 (`tools/terminal.py` + `tools/registry.py`) may begin after all four criteria are met.
