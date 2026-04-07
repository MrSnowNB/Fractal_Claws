# Fractal Claws — AI Onboarding Context

> **Read this file first.** It gives you everything you need to understand what
> this system does, where it is right now, and what rules you must follow.
> After reading this file, read `AI-FIRST/ARCHITECTURE.md` then
> `AI-FIRST/NEXT-STEPS.md`.

---

## What This System Is

Fractal Claws is a **local agentic harness** for running multi-step AI tasks
without cloud infrastructure. A parent agent (Cline in VS Code) decomposes a
human goal into discrete tickets. A child runner (`agent/runner.py`) picks up
those tickets, executes tool calls, writes results, and closes the tickets.
Everything runs on local hardware via an OpenAI-compatible endpoint
(Lemonade, Ollama, or LM Studio).

**The core loop:**
```
Human gives goal
  → parent decomposes into tickets/open/*.yaml
  → runner picks up tickets in dependency order
  → runner calls tools (read_file, write_file, exec_python, list_dir)
  → runner writes result to logs/<id>-result.txt
  → runner closes ticket to tickets/closed/<id>.yaml
  → parent reads result, continues or escalates
```

---

## Current Validated State (Gate: 2026-04-07)

The ticketing system reached a **validated gate** on 2026-04-07. This means:

- The `Ticket` dataclass (`src/operator_v7.py`) is stable and tested
- The 5-phase multistep harness passes 6/6 in `tests/test_multistep_harness.py`
- The runner correctly detects dependency deadlocks
- Parent/child ticket wiring is proven end-to-end

This gate is the **foundation** for Phase 3 (OpenClaw tool registry). Do not
refactor the `Ticket` dataclass or the ticket lifecycle without running the
full gate first.

---

## Critical Facts (Do Not Get These Wrong)

1. **There is no `Operator` class.** `src/operator_v7.py` defines `Ticket`,
   `TicketStatus`, `TicketPriority`, `TicketDepth` only. The file is named
   `operator_v7.py` for historical reasons but contains no `Operator` class.

2. **Runtime tickets are gitignored.** `tickets/open/*.yaml` and
   `tickets/in_progress/*.yaml` do not live in the repo. You cannot commit
   them. Place test tickets manually or generate via `python agent/runner.py
   --goal "<your goal>"`.

3. **Import pattern requires `sys.path.insert`.** All test files and scripts
   must add `src/` to `sys.path` before importing from `operator_v7`:
   ```python
   sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
   from operator_v7 import Ticket, TicketStatus, TicketPriority
   ```

4. **Depth 2 (LEAF) is reserved / deprecated.** The 4B model slot assigned
   to depth=2 has been removed. Do not assign tasks to depth=2 until NPU
   integration is re-enabled.

5. **The runner implements deadlock detection.** If TASK-003 depends on
   TASK-002 and TASK-002 was never placed in `tickets/open/`, the runner
   will print the blocked dependency graph and exit 1. This is correct
   behavior, not a bug.

6. **Audit logs are append-only JSONL.** `logs/<id>-attempts.jsonl` must
   never be rewritten. One JSON object per line, one line per attempt.

---

## Repository Owner

MrSnowNB. Hardware: RTX 6000 ADA workstation, Windows 11. Local inference
via Lemonade (primary) or Ollama. Python 3.10.11. pytest 7.4.3.

---

## Files You Will Touch Most

| File | Purpose |
|---|---|
| `src/operator_v7.py` | Ticket dataclass — the type layer |
| `agent/runner.py` | Decompose + drain loop |
| `tickets/template.yaml` | Ticket schema |
| `settings.yaml` | Model endpoint config |
| `tests/test_multistep_harness.py` | Primary regression gate |
| `CLAUDE.md` | Cline session instructions |
| `OPENCLAW-PLAN.md` | Phase 3 plan |

---

## What You Must Not Do

- Do not create an `Operator` class
- Do not hardcode model names in `agent/runner.py`
- Do not rewrite `logs/*.jsonl` files
- Do not push without running `pytest tests/test_multistep_harness.py -v` first
- Do not assign work to depth=2 (LEAF) until NPU integration is re-enabled
- Do not import from `src.operator_v7` with the `src.` prefix — use
  `sys.path.insert` and import `from operator_v7 import ...`

---

## How to Give Yourself More Context

```
AI-FIRST/ARCHITECTURE.md  — dataclass fields, ticket lifecycle, module inventory
AI-FIRST/NEXT-STEPS.md    — Phase 3 roadmap, open tasks, entry points
OPENCLAW-PLAN.md          — full Phase 3 specification
VISION.md                 — long-range project direction
TROUBLESHOOTING.md        — known failure modes and fixes
```
