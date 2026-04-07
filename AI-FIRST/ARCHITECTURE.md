# Fractal Claws — Architecture Reference

> Read `AI-FIRST/CONTEXT.md` before this file.

---

## Core Type Layer: `src/operator_v7.py`

This module is the **canonical type layer** for Phase 3. The runner currently
treats tickets as raw dicts loaded from YAML. Phase 3 will wire these dataclasses
into `load_ticket()` / `save_ticket()` for schema validation and type safety.

### Enums

```python
class TicketStatus(Enum):
    PENDING    = "pending"
    ESCALATED  = "escalated"
    CLOSED     = "closed"

class TicketPriority(Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

class TicketDepth(Enum):
    ROOT    = 0   # Orchestrator — Qwen3-Coder-Next-GGUF
    WORKER  = 1   # Subtask execution — Qwen3.5-35B-A3B-GGUF
    LEAF    = 2   # Reserved for NPU — deprecated until re-enabled
```

### Ticket Dataclass

```python
@dataclass
class Ticket:
    id: str
    depth: int = 0
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    status: TicketStatus = TicketStatus.PENDING
    attempts: int = 0
    decrement: int = 3          # escalation decrements remaining
    priority: TicketPriority = TicketPriority.MEDIUM
    result: Dict[str, Any] = field(default_factory=dict)
    created_at: str             # ISO 8601, auto-set on construction
```

**Key methods:**
- `Ticket.from_dict(data: dict) -> Ticket` — deserialize from YAML/JSON dict
- `ticket.to_dict() -> dict` — serialize back to YAML/JSON dict

### Construction Pattern

```python
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
# ticket.status == TicketStatus.PENDING
# ticket.priority == TicketPriority.HIGH
```

---

## Ticket Lifecycle (On-Disk)

```
tickets/
├── template.yaml       ← schema reference, copy this to create tickets
├── open/               ← GITIGNORED at runtime — parent writes here
├── in_progress/        ← runner moves ticket here on pickup
├── closed/             ← runner moves ticket here on PASS
└── failed/             ← runner moves ticket here on max depth exceeded
```

**State transitions:**
```
open → in_progress   (runner picks up)
in_progress → closed  (tool calls complete, result written, status=CLOSED)
in_progress → failed  (attempts >= decrement, no more escalation)
open → deferred       (depends_on not yet satisfied — stays in open/)
```

**Deadlock condition:** All remaining open tickets are deferred (every ticket
has at least one unsatisfied dependency). Runner prints the dependency graph
and exits 1. This is expected and correct.

---

## Dependency Graph

Tickets declare dependencies via `depends_on: [TASK-XYZ, ...]` in their YAML.
The runner reads `tickets/closed/` to determine which IDs are satisfied.

Example:
```yaml
# TASK-003.yaml
ticket_id: TASK-003
depends_on:
  - TASK-002
```
TASK-003 will be deferred until `tickets/closed/TASK-002.yaml` exists.

---

## Audit Log Format

Location: `logs/<ticket_id>-attempts.jsonl`

Each attempt appends exactly one JSON line:
```json
{
  "ts": "2026-04-07T07:30:00",
  "attempt": 1,
  "outcome": "pass",
  "tokens": 412,
  "elapsed_s": 3.2,
  "finish": "stop"
}
```

Rules:
- Append-only. Never rewrite or truncate.
- `outcome` values: `"pass"`, `"fail"`, `"escalate"`
- Monitor live: `tail -f logs/*.jsonl`

---

## Module Inventory

| Module | Exports | Notes |
|---|---|---|
| `src/operator_v7.py` | `Ticket`, `TicketStatus`, `TicketPriority`, `TicketDepth` | Type layer. No `Operator` class. |
| `src/tools/first_principles_solver.py` | `FirstPrinciplesAnalyzer`, `RecursiveSolver`, `SelfHealingMechanism` | Imported by `operator_v7` |
| `agent/runner.py` | CLI entrypoints `--goal`, `--once`, `--no-prewarm` | Drain loop + decomposer |
| `tools/read_file.py` | `read_file(path)` | Child tool — sandboxed |
| `tools/write_file.py` | `write_file(path, content)` | Child tool — sandboxed |
| `pre_flight.py` | `run_checks()` | Endpoint + dep health check |
| `init.py` | Setup bootstrap | Run once after clone |

---

## Test Inventory

| Test file | What it covers | Gate? |
|---|---|---|
| `tests/test_multistep_harness.py` | 5-phase parent/child pipeline, HarnessTrace | **PRIMARY GATE** |
| `tests/test_operator.py` | Ticket dataclass construction, serialization | Supporting |
| `tests/test_harness_artifacts.py` | File artifact existence checks | Supporting |
| `tests/test_first_principles_solver.py` | Solver module | Supporting |
| `tests/test_solver_init.py` | Solver init | Supporting |

**Gate command:**
```bash
pytest tests/test_multistep_harness.py -v
# Expected: 6/6 passed
```

---

## Model Depth Map

| TicketDepth | Value | Current model | Status |
|---|---|---|---|
| ROOT | 0 | Qwen3-Coder-Next-GGUF | Active |
| WORKER | 1 | Qwen3.5-35B-A3B-GGUF | Active |
| LEAF | 2 | TBD | **Deprecated / reserved** |

Depth is assigned at ticket creation. The runner reads `settings.yaml` to map
depth integer to the model endpoint string. Never hardcode model names in
`agent/runner.py`.

---

## Settings Schema (`settings.yaml`)

```yaml
model:
  endpoint: http://localhost:8080/v1   # OpenAI-compatible base URL
  id: Qwen3-Coder-Next-GGUF           # sent as model= in API calls
  depth_map:
    0: Qwen3-Coder-Next-GGUF
    1: Qwen3.5-35B-A3B-GGUF
    2: null                            # reserved
runner:
  max_turns: 12
  timeout_s: 120
  prewarm: true
```
