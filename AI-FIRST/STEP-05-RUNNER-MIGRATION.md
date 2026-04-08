# Step 5 — Full Runner Migration to Typed Ticket Access

> **AI-FIRST SPEC** — Read `AI-FIRST/CONTEXT.md` before this file.
> This spec is self-contained. Follow it ticket by ticket in order.
> Do not start a ticket until its dependency (if any) is closed.

---

## Goal

Eliminate all raw-dict access to ticket fields in `agent/runner.py`.
After this step, the runner treats every ticket as a typed `Ticket` dataclass.
No more `ticket.get("field")`. No more `as_dict()` shim calls inside runner logic.
The shim may remain in `src/ticket_io.py` for backward-compat serialization,
but the runner itself must never call it for read access.

**Why this matters (first principles):**
The `Ticket` dataclass is the system's type contract. Every field has a type,
a default, and validation logic in `from_dict()`. A runner that reads raw dicts
bypasses all of that — it can silently read a missing key as `None` instead of
raising a schema error. Typed access makes the contract visible at the call site
and lets the test suite catch regressions immediately.

---

## Invariants This Step Must Preserve

1. `pytest tests/ -v` — full suite green before and after every commit
2. `logs/luffy-journal.jsonl` — valid JSONL, one entry per commit
3. All existing ticket lifecycle behavior (open → in_progress → closed/failed)
4. All existing audit log behavior (append-only JSONL per ticket)
5. `REGISTRY.call()` dispatch — not reverted to if/elif
6. `depends_on` deadlock detection — not broken
7. No hardcoded model names introduced

**If any invariant is at risk, stop. Document in TROUBLESHOOTING.md. Ask.**

---

## Tickets

### STEP-05-A: Audit All Dict Access in runner.py

```yaml
ticket_id: STEP-05-A
task: >
  Read agent/runner.py in full. Produce a structured audit of every location
  where ticket fields are accessed as raw dict keys (ticket.get("x"), ticket["x"],
  ticket.get("x", default)). For each hit, record:
    - line number
    - field name
    - current access pattern
    - typed equivalent (ticket.x or ticket.x if ticket.x else default)
  Write the audit to logs/STEP-05-audit.txt in markdown table format.
  Do not modify runner.py yet.
depends_on: []
gate: logs/STEP-05-audit.txt exists and lists every dict-access call site
```

**Why first:** You cannot migrate what you have not mapped.
The audit is the diff between current state and required state.
Do not guess — read the actual file.

---

### STEP-05-B: Migrate load_ticket() to Return Ticket Directly

```yaml
ticket_id: STEP-05-B
task: >
  Refactor load_ticket() in agent/runner.py so it returns a Ticket dataclass
  directly (via ticket_io.load_ticket() or Ticket.from_dict()) instead of a raw dict.
  Update all call sites that receive the return value.
  Ensure the typed object flows into drain(), execute_ticket(), and decompose().
  Write or update tests in tests/test_runner_dispatch.py to assert that
  load_ticket() returns a Ticket instance, not a dict.
depends_on: [STEP-05-A]
gate: pytest tests/test_runner_dispatch.py -v — all green, new isinstance(ticket, Ticket) assertion passing
```

**Constraint:** Do not change the on-disk YAML format. The ticket YAML files
are the contract with the parent agent (Cline). The migration is internal to runner.py.

---

### STEP-05-C: Replace All Dict Access Call Sites

```yaml
ticket_id: STEP-05-C
task: >
  Using the audit from STEP-05-A as the work order, replace every
  ticket.get("field") and ticket["field"] call site in agent/runner.py
  with ticket.field attribute access.
  Handle optional fields explicitly:
    - ticket.depends_on if hasattr(ticket, 'depends_on') else []
    - or add depends_on: List[str] = field(default_factory=list) to the dataclass
  After all replacements, remove any import or usage of as_dict() shim
  from runner.py that was used for read access (serialization usage may remain).
depends_on: [STEP-05-B]
gate: >
  pytest tests/ -v — full suite green.
  grep -n 'ticket.get\|ticket\[' agent/runner.py returns zero hits.
```

---

### STEP-05-D: Gate, Journal, Commit

```yaml
ticket_id: STEP-05-D
task: >
  Run the full gate: pytest tests/ -v
  Confirm zero dict-access call sites remain in runner.py.
  Write a gate summary to logs/STEP-05-gate.txt:
    - test count and pass rate
    - dict-access call sites removed (count from audit vs. count after)
    - any optional fields added to Ticket dataclass
  Append journal entry to logs/luffy-journal.jsonl.
  git add agent/runner.py src/operator_v7.py tests/test_runner_dispatch.py
       logs/STEP-05-audit.txt logs/STEP-05-gate.txt logs/luffy-journal.jsonl
  git commit -m "STEP-05: full typed field access in runner.py — dict shim removed"
  git push
depends_on: [STEP-05-C]
gate: git push succeeds, journal entry valid, pytest tests/ green
```

---

## What to Watch For

### Optional fields not on Ticket dataclass

Some fields written into ticket YAML by Cline (e.g. `depends_on`, `context_files`,
`result_path`, `task`) may not be declared on the `Ticket` dataclass yet.
If `Ticket.from_dict()` drops unknown fields silently, the runner will lose them.

**First principles fix:** Before migrating a call site, check whether the field
exists on the dataclass. If it doesn't, add it with a safe default:
```python
# In src/operator_v7.py
depends_on: List[str] = field(default_factory=list)
context_files: List[str] = field(default_factory=list)
result_path: Optional[str] = None
task: Optional[str] = None
```
Then run `pytest tests/` before touching runner.py call sites.

### as_dict() shim

The `as_dict()` shim in `src/ticket_io.py` exists for serialization back to YAML.
Do not remove it from `ticket_io.py`. Remove only its usage inside runner.py
for **read access**. Serialization (save_ticket, write YAML) may still use it.

### Deadlock detection relies on ticket.id

The dependency graph walk reads `ticket.id` to match against `depends_on` lists.
Confirm `ticket.id` is the correct attribute name (not `ticket_id`) after migration.
If the dataclass uses `id` but the YAML key is `ticket_id`, `from_dict()` must
map `ticket_id` → `id`. Verify this in STEP-05-A audit.

---

## Validation Gate (Final)

```bash
# 1. Full test suite
pytest tests/ -v
# Expected: all green (currently 13+11+14 = 38+ tests)

# 2. Zero dict-access call sites
grep -n 'ticket\.get\|ticket\[' agent/runner.py
# Expected: no output

# 3. Journal valid
python -c "
import json
for i, line in enumerate(open('logs/luffy-journal.jsonl'), 1):
    line = line.strip()
    if line: json.loads(line)
print('Journal: all lines valid')
"

# 4. Step 5 gate file exists
test -f logs/STEP-05-gate.txt && echo 'Gate file: present'
```

All four checks must pass before Step 5 is marked DONE.

---

## Step 6 Preview (Do Not Build Yet)

Once runner.py is fully typed:
- **Skill-aware decomposition** — before decomposing a goal, runner reads `skills/`
  and short-circuits if a matching goal class exists, running the cached toolpath directly
- **Typed result writing** — `ticket.result` dict replaced with a typed `TicketResult` dataclass
- **OpenClaw spawning** — `delegate_task` tool triggers a real child process
  on a second GPU with depth=1 model

Step 5 is the prerequisite for all of these. A runner that reads typed fields
can be extended cleanly. A runner that reads raw dicts cannot.

---

*Spec version: 1.0*  
*Written: 2026-04-07*  
*Maintained by: Mark Snow + Luffy*
