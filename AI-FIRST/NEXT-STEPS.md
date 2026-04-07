# Fractal Claws — Next Steps (Phase 3)

> Read `AI-FIRST/CONTEXT.md` and `AI-FIRST/ARCHITECTURE.md` before this file.

---

## Where We Are

The validated gate (2026-04-07) confirmed:

- `Ticket` dataclass is stable (`from_dict` / `to_dict` round-trip proven)
- 5-phase multistep harness passes 6/6
- Deadlock detection works correctly
- Ticket lifecycle (open → in_progress → closed/failed) is implemented in runner

The runner currently treats tickets as **raw dicts** loaded from YAML. Phase 3
wires the `Ticket` dataclass into the runner for schema validation and type safety.

---

## Phase 3: OpenClaw Tool Registry

Full specification in `OPENCLAW-PLAN.md`. Summary of entry points:

### 3.1 Wire Ticket Dataclass into Runner

**Target file:** `agent/runner.py`

**What to change:**
- Replace raw `yaml.safe_load()` dict handling with `Ticket.from_dict()`
- Add `load_ticket(path: Path) -> Ticket` and `save_ticket(ticket: Ticket, path: Path)` helpers
- All internal runner logic should operate on `Ticket` objects, not dicts
- `ticket.to_dict()` when writing back to YAML

**Acceptance test:** Existing gate (`tests/test_multistep_harness.py`) must
still pass 6/6 after this change. No new failures.

### 3.2 Tool Call Schema Validation

**Target files:** `tools/read_file.py`, `tools/write_file.py`, new `tools/exec_python.py`

**What to add:**
- Each tool exposes a JSON Schema in a `TOOL_SCHEMA` dict
- Runner validates tool call args against schema before dispatch
- Invalid args raise `ToolValidationError` (new exception class in `src/`)
- Add `tests/test_tool_registry.py` to cover schema validation

### 3.3 Result Validation Gate

**Target file:** `agent/runner.py`

**What to add:**
- After child writes `logs/<id>-result.txt`, runner validates the result file exists
- Runner reads the result and checks for a `PASS` or `FAIL` verdict line
- On `FAIL`: increment `ticket.attempts`, decrement `ticket.decrement`;
  if `decrement == 0`, move to `tickets/failed/`; else re-queue
- On `PASS`: set `ticket.status = TicketStatus.CLOSED`, move to `tickets/closed/`

### 3.4 HarnessTrace Integration (Optional)

**Target file:** `agent/runner.py`

**What to add:**
- Import `HarnessTrace` and `_stamp` from `tests/test_multistep_harness.py`
  (or extract to `src/trace.py`)
- Runner stamps a trace event at every major state transition
- Trace written to `logs/<id>-trace.jsonl` alongside the attempts log
- Enables post-mortem inspection of live runs, not just test runs

---

## Open Issues

| Issue | File | Priority |
|---|---|---|
| Runtime tickets absent from repo due to `.gitignore` | `tickets/open/` | Medium — use `--goal` to generate |
| `session.jsonl` still tracked in git | `experiments/daemon/logs/session.jsonl` | Low — `git rm --cached` it |
| Depth=2 (LEAF) model slot unassigned | `settings.yaml` | Deferred until NPU |
| `conftest.py` fixture uses `Ticket` but no `test_mode` param | `tests/conftest.py` | Low |

---

## Pre-Phase-3 Checklist

Before writing any Phase 3 code, verify:

```powershell
# Full gate must be green
pytest tests/ -v

# Deadlock smoke test
python agent/runner.py --no-prewarm

# No import errors
python -c "import sys; sys.path.insert(0, 'src'); from operator_v7 import Ticket, TicketStatus, TicketPriority; print('OK')"
```

All three must pass before touching `agent/runner.py`.

---

## Suggested First Task for a New Agent

If you are a new AI assistant and want a concrete first task:

**Task:** Implement `load_ticket(path: Path) -> Ticket` and
`save_ticket(ticket: Ticket, path: Path) -> None` as standalone functions
in a new file `src/ticket_io.py`. These should wrap `yaml.safe_load` /
`yaml.dump` with `Ticket.from_dict()` / `ticket.to_dict()`. Add
`tests/test_ticket_io.py` that round-trips a ticket through write → read
and asserts all fields are preserved.

This is a self-contained, low-risk entry point that does not touch the runner
or the existing gate tests.
