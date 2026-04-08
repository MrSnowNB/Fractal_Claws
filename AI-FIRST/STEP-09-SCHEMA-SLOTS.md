# STEP-09 — Schema Slots: Three Fields, One Contract

> **AI-FIRST DOC** — Minimal, clean, expandable.
> This is the complete STEP-09 scope. Do not add spawning mechanics,
> parallel execution, or orchestration logic. Those belong to STEP-11+.

---

## What STEP-09 Delivers

Three nullable schema fields and one formal document.
Nothing else.

| Deliverable | File | What it enables later |
|---|---|---|
| `graph_scope` field in ticket schema | `src/ticket_io.py` | Parent sets child's subgraph scope automatically |
| `return_to` field in ticket schema | `src/ticket_io.py` | Parent event loop wakeup |
| `agent_id` field in journal schema | `scripts/log_journal.py` | Multi-agent log attribution |
| Birth package formal contract | `AI-FIRST/AGENT-PERSONA.md` | Any model can cold-start as a child |

---

## Sub-ticket A — Ticket Schema: `graph_scope` (nullable)

Add to `Ticket` in `src/ticket_io.py`:

```python
# graph_scope: optional — parent sets the child's subgraph
# null today, filled by automated Key-Brain later
graph_scope: dict | None = None
# schema:
# graph_scope:
#   seed_nodes: ["function:prune_logs", "file:agent/runner.py"]
#   depth: 2
#   node_types: ["function", "file", "ticket"]
```

**Rule:** If `graph_scope` is null, child defaults to ticket-scoped query.
Parent may populate it with any subset. Field is always present in
`ticket.to_dict()` output (serialized as `null` if unset).

**Anti-pattern to avoid:** Do NOT let children determine their own graph
scope from scratch on every run. The parent decomposed the problem — it
knows which subgraph matters. `graph_scope` is where that intelligence lands.

---

## Sub-ticket B — Ticket Schema: `return_to` (nullable)

Add to `Ticket` in `src/ticket_io.py`:

```python
# return_to: optional — who wakes up when this child finishes
# null = no wakeup needed (manual inspection)
# "parent" = parent event loop
# "TASK-043" = sibling dependency
return_to: str | None = None
```

**Rule:** Field is always present in `ticket.to_dict()` output.
Round-trip (`from_dict(to_dict())`) must preserve `None`.

---

## Sub-ticket C — Journal Schema: `agent_id` (optional)

Update `append_journal()` in `scripts/log_journal.py`:

```python
def append_journal(record: dict, agent_id: str = "luffy-v1") -> None:
    record.setdefault("agent_id", agent_id)
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    ...
```

**Rule:** Every record written to `luffy-journal.jsonl` must have `agent_id`.
Default is `"luffy-v1"`. When children get IDs (STEP-11+), they pass
`agent_id="luffy-child-TASK-042"` at call time.

Update journal entry schema in `AGENT-PERSONA.md` to include `agent_id`.

---

## Sub-ticket D — Birth Package Formal Contract

The birth package is the complete context handoff from parent to child.
It is defined in `AGENT-PERSONA.md`. Any model that reads the birth package
can orient and execute — no Luffy-specific knowledge required.

See `AGENT-PERSONA.md` → **Birth Package Contract** section for the
full formal definition.

**Hard rules:**
- Parent memory MUST NOT appear in any birth package file
- `anchor.json` → `system_state` is a **string** (one sentence), not a dict
- The 5-file schema is fixed — do not add files without a spec change
- `tool_registry.yaml` MUST NOT contain `spawn_child` or `delegate_task`

---

## Gate Criteria

```
[ ] Ticket.to_dict() includes graph_scope (null if unset)
[ ] Ticket.to_dict() includes return_to (null if unset)
[ ] Ticket round-trip (from_dict(to_dict())) preserves both new fields
[ ] append_journal() writes agent_id on every record
[ ] append_journal() defaults agent_id to "luffy-v1"
[ ] AGENT-PERSONA.md has Birth Package Contract section
[ ] AGENT-PERSONA.md journal schema includes agent_id field
[ ] anchor.json system_state is documented as string, not dict
[ ] All existing tests pass — 0 regressions
[ ] No spawning mechanics added
[ ] No orchestration loop added
[ ] No process management added
```

---

## What STEP-09 Does NOT Touch

- Agent spawning mechanics
- Parallel execution / locking
- Child model selection
- Specialization / fine-tuning
- `query_graph` depth/node_type filtering (STEP-10 — Graphify)
- Any actual `luffy.py` orchestration loop
- `child_runner.py`
- `birth_writer.py`

Those all belong to STEP-10 (Graphify) or STEP-11 (Orchestration Layer).

---

## Principle

> Build the slots now, fill them later.
> Nullable fields in a typed schema cost nothing.
> Missing fields in a shipped schema require a migration.
> The architectural debt of a missing `agent_id` field is trivial today
> and expensive when you have 10 concurrent children writing to the same journal.
