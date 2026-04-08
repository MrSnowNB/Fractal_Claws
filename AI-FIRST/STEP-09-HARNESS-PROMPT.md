# STEP-09 Harness Prompt

> Feed this file to Luffy verbatim as her task prompt.
> She reads `AGENT-PERSONA.md`, orients from the journal anchor, then executes.

---

## Cold-Start State Summary

Read `AI-FIRST/AGENT-PERSONA.md` now. Then act on the following state summary.

---

COLD-START ANCHOR (from `logs/luffy-journal.jsonl` — last entry):

```
step:   STEP-08E-F
status: green
tests:  194 passed, 5 skipped, 0 failed

system_state: STEP-08E complete. drain() and execute_ticket()
call prune_logs() with settings.yaml config; all 194 tests pass.

next_entry_point: STEP-09 — schema slots.
```

---

## ACTIVE STEP: STEP-09

Full spec: `AI-FIRST/STEP-09-SCHEMA-SLOTS.md`
Complete all sub-tickets in order. Do not jump ahead.

Sub-tickets:

- **STEP-09-A** — Add `graph_scope: dict | None = None` to `Ticket` in `src/ticket_io.py`
- **STEP-09-B** — Add `return_to: str | None = None` to `Ticket` in `src/ticket_io.py`
- **STEP-09-C** — Verify round-trip: `Ticket.from_dict(ticket.to_dict()) == ticket` still holds for both new fields
- **STEP-09-D** — `append_journal()` in `scripts/log_journal.py` already updated — verify `agent_id` is written on all existing test journal calls
- **STEP-09-E** — Update `tests/test_ticket_io.py` to assert `graph_scope` and `return_to` survive round-trip (null → null, value → value)
- **STEP-09-F** — Update `tests/test_step09_schema.py` (NEW file) with journal `agent_id` assertions

---

## Gate

Before committing:

```
[ ] pytest tests/ -v — 0 failed, regressions = 0
[ ] ticket.to_dict() has graph_scope key (null if unset)
[ ] ticket.to_dict() has return_to key (null if unset)
[ ] round-trip preserves null and non-null values for both fields
[ ] append_journal() writes agent_id = "luffy-v1" by default
[ ] journal entry has agent_id in every test that calls append_journal()
[ ] No child_runner.py created
[ ] No birth_writer.py created
[ ] No luffy.py orchestration loop added
[ ] No spawning or process management added
```

---

## Luffy Law

Journal first. Gate green. Then commit.

agent_id on every journal entry from this step forward.
