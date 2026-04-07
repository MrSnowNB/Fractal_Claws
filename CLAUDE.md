# Fractal Claws — Cline Harness Guide

This file is read by Cline automatically at session start.
Keep it accurate. Last validated: **2026-04-07**.

---

## Current State (Validated Gate)

The ticketing system is **fully validated** as of 2026-04-07.

- `src/operator_v7.py` defines the canonical `Ticket` dataclass (no `Operator` class exists)
- `agent/runner.py` handles decompose → drain → dependency graph → close
- `tests/test_multistep_harness.py` is the primary regression gate — 6/6 green
- Deadlock detection is working: runner correctly defers tickets with unmet deps

**Do not create an `Operator` class.** The pattern is `Ticket.from_dict()` directly.

---

## Before Every Push

```powershell
# Primary gate — must be green before any push touching src/ or agent/
pytest tests/test_multistep_harness.py -v

# Full suite
pytest tests/ -v

# Deadlock detection smoke test
python agent/runner.py --no-prewarm
```

### Reading a Harness Failure

When `test_multistep_harness.py` fails, the assertion message includes the full
`HarnessTrace` JSON. Read it phase by phase:

- `status=started` with no `status=completed` for the same phase — the phase never finished
- `status=failed` — the phase completed but produced a bad result; check the `extra` fields
- Missing phase entirely — an earlier phase raised before it could record the stamp

```
pytest tests/test_multistep_harness.py -v
pytest tests/test_multistep_harness.py::TestFullPipeline -v
pytest tests/test_multistep_harness.py -v -k TestPhase3
```

---

## Ticket Conventions

```yaml
# tickets/template.yaml shape
ticket_id: TASK-001
task: "<imperative sentence describing the work>"
context_files:
  - path/to/relevant/file.py
depends_on: []          # list of ticket_ids that must be closed first
result_path: logs/TASK-001-result.txt
max_depth: 2
```

**Runtime tickets are gitignored.** `tickets/open/*.yaml` and
`tickets/in_progress/*.yaml` do not commit. Place test tickets manually
or generate them via `--goal`.

---

## Module Map (Quick Reference)

| File | What it contains |
|---|---|
| `src/operator_v7.py` | `Ticket`, `TicketStatus`, `TicketPriority`, `TicketDepth` dataclass + enums |
| `agent/runner.py` | Goal decomposer + ticket queue drain loop |
| `tools/read_file.py` | Sandboxed file reader (child tool) |
| `tools/write_file.py` | Sandboxed file writer (child tool) |
| `pre_flight.py` | Endpoint + dependency health check |
| `settings.yaml` | Model endpoint, depth map, timeouts |
| `tests/test_multistep_harness.py` | **Primary gate** — 5-phase parent/child pipeline |
| `tests/conftest.py` | `ticket` fixture: `Ticket(test_mode=True)` |

---

## Import Pattern (Tests and Scripts)

```python
# Always bootstrap path before importing from src/
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operator_v7 import Ticket, TicketStatus, TicketPriority

# Construct directly — no Operator class
ticket = Ticket.from_dict({
    "id": "TASK-001",
    "depth": 0,
    "priority": "high",
    "status": "pending",
    "attempts": 0,
    "decrement": 3,
    "parent": None,
    "children": [],
    "result": {},
})
```

---

## Model Depth Map

| Depth | Role | Model slot |
|---|---|---|
| 0 | ROOT / Orchestrator | `Qwen3-Coder-Next-GGUF` |
| 1 | WORKER / Subtask execution | `Qwen3.5-35B-A3B-GGUF` |
| 2 | LEAF / NPU (reserved) | TBD — see settings.yaml |

The 4B model slot is **deprecated**. Do not assign work to depth=2 until NPU
integration is re-enabled.

---

## Phase 3 Entry Point

Next build target is the **OpenClaw tool registry** (see `OPENCLAW-PLAN.md`):
- Wire `Ticket` dataclass into `load_ticket()` / `save_ticket()` in `agent/runner.py`
- Replace raw dict handling with typed `Ticket` objects throughout the runner
- Add tool call schema validation against `tools/` registry

Do not start Phase 3 without running the full gate first.
