# Fractal Claws — Architecture Reference

> Read `AI-FIRST/CONTEXT.md` before this file.

---

## Core Type Layer: `src/operator_v7.py`

This module is the **canonical type layer** for Phase 3. Step 5 completes the
migration: `agent/runner.py` will read all ticket fields as typed attributes,
not raw dict keys.

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
    # Fields added for Step 5 migration (may already be present):
    depends_on: List[str] = field(default_factory=list)
    context_files: List[str] = field(default_factory=list)
    result_path: Optional[str] = None
    task: Optional[str] = None
```

**Step 5 migration note:** Before replacing any `ticket.get("field")` call site,
verify the field is declared here. If it is not, add it with a safe default
before touching `agent/runner.py`.

**Key methods:**
- `Ticket.from_dict(data: dict) -> Ticket` — deserialize from YAML/JSON dict
- `ticket.to_dict() -> dict` — serialize back to YAML/JSON dict

**YAML key mapping:** The YAML key is `ticket_id`. `from_dict()` must map
`ticket_id` → `id`. Verify this mapping exists before Step 5 migration.

### Construction Pattern

```python
ticket = Ticket.from_dict({
    "ticket_id": "TASK-001",
    "depth": 0,
    "priority": "high",
    "status": "pending",
    "attempts": 0,
    "decrement": 3,
    "parent": None,
    "children": [],
    "result": {},
})
# ticket.id == "TASK-001"
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

**Deadlock condition:** All remaining open tickets are deferred.
Runner prints the dependency graph and exits 1.

---

## Dependency Graph

Tickets declare dependencies via `depends_on: [TASK-XYZ, ...]` in their YAML.
The runner reads `tickets/closed/` to determine which IDs are satisfied.

**Step 5 migration:** `depends_on` must be a declared field on `Ticket`.
After migration, the dependency check reads `ticket.depends_on` (typed list),
not `ticket.get("depends_on", [])`.

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
| `src/ticket_io.py` | `load_ticket()`, `save_ticket()`, `scan_dir()`, `as_dict()` shim | Step 5: shim stays here for serialization |
| `src/trajectory_extractor.py` | `extract_trajectory()`, `write_skill()`, `run_extraction()` | Step 4 complete |
| `agent/runner.py` | CLI entrypoints `--goal`, `--once`, `--no-prewarm` | Step 5: dict access → typed access |
| `tools/registry.py` | `ToolRegistry`, `REGISTRY` singleton | Dynamic dispatch |
| `tools/terminal.py` | `run_command()` | subprocess + DANGEROUS_PATTERNS denylist |
| `tools/read_file.py` | `read_file(path)` | Child tool — sandboxed |
| `tools/write_file.py` | `write_file(path, content)` | Child tool — sandboxed |
| `pre_flight.py` | `run_checks()` | Endpoint + dep health check |
| `skills/` | `<goal-class>.yaml` files | Executable memory — written by trajectory extractor |

---

## Test Inventory

| Test file | What it covers | Gate |
|---|---|---|
| `tests/test_ticket_io.py` | Typed ticket loading, enum coercion, as_dict shim | Step 1 ✅ |
| `tests/test_tools.py` | Terminal denylist, registry dispatch, schema validation | Step 2 ✅ 14/14 |
| `tests/test_runner_dispatch.py` | REGISTRY wiring, ticket_io integration | Step 3 ✅ 11/11 |
| `tests/test_trajectory.py` | Trajectory extractor, skill writing | Step 4 ✅ 13/13 |
| `tests/test_runner_dispatch.py` | Step 5 will add: isinstance(ticket, Ticket) assertions | Step 5 target |
| `tests/test_multistep_harness.py` | 5-phase parent/child pipeline, HarnessTrace | PRIMARY GATE |

**Full gate command:**
```bash
pytest tests/ -v
# Expected: 38+ tests, all green
```

---

## Skills Directory — Executable Memory

`skills/<goal-class>.yaml` is the output of the trajectory extractor.
Each file encodes the winning toolpath for a known goal class:

```yaml
goal_class: write-file-and-test
first_pass_attempt: 1
tools_used: [read_file, write_file, exec_python]
elapsed_s: 4.1
tokens: 512
produces: ["tests/*.py", "src/*.py"]
consumes: ["tickets/*.yaml"]
```

Cline reads `skills/` before decomposing a new goal. If the goal class matches,
decomposition is skipped and the toolpath runs directly. This is the self-improving
loop that gets faster with every passing run.

**Design requirement:** Every skill YAML must be machine-actionable — structured
so any agent instance can read it and reconstruct the execution plan without
asking for clarification. Same discipline as AI-FIRST docs.

---

## Model Depth Map

| TicketDepth | Value | Current model | Status |
|---|---|---|---|
| ROOT | 0 | Qwen3-Coder-Next-GGUF | Active |
| WORKER | 1 | Qwen3.5-35B-A3B-GGUF | Active |
| LEAF | 2 | TBD | **Deprecated / reserved** |

Depth is assigned at ticket creation. The runner reads `settings.yaml` to map
depth integer to model endpoint string. Never hardcode model names in `agent/runner.py`.

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
