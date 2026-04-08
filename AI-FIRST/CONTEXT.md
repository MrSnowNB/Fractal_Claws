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
  → runner calls tools via REGISTRY.call() (dynamic dispatch)
  → runner writes result to logs/<id>-result.txt
  → runner closes ticket to tickets/closed/<id>.yaml
  → parent reads result, continues or escalates
```

---

## Current Validated State (Gate: 2026-04-07)

| Step | What was built | Gate |
|---|---|---|
| Step 1 | `src/ticket_io.py` — typed Ticket loader + `as_dict()` shim | `pytest tests/test_ticket_io.py` ✅ |
| Step 2 | `tools/terminal.py` + `tools/registry.py` | `pytest tests/test_tools.py` ✅ 14/14 |
| Step 3 | Registry wired into `agent/runner.py`; `parse_and_run_tools()` uses `REGISTRY.call()` | `pytest tests/test_runner_dispatch.py` ✅ 11/11 |
| Step 4 | `src/trajectory_extractor.py` | `pytest tests/test_trajectory.py` — **active** |

**Do not refactor the `Ticket` dataclass or the ticket lifecycle without running
the full gate (`pytest tests/ -v`) first.**

---

## Luffy Law — Commit Protocol (MANDATORY)

> **Journal first. Always.**
>
> Before every `git commit`:
> 1. `pytest tests/` — all green
> 2. Append entry to `logs/luffy-journal.jsonl`
> 3. `git add <files> logs/luffy-journal.jsonl`
> 4. `git commit`
> 5. `git push`
>
> Entry schema:
> ```json
> {"ts": "ISO-8601", "step": "STEP-XX-Y", "action": "...", "status": "done", "files": [...]}
> ```

---

## Critical Facts (Do Not Get These Wrong)

1. **There is no `Operator` class.** `src/operator_v7.py` defines `Ticket`,
   `TicketStatus`, `TicketPriority`, `TicketDepth` only.

2. **Runtime tickets are gitignored.** `tickets/open/*.yaml` and
   `tickets/in_progress/*.yaml` do not live in the repo.

3. **Import pattern requires `sys.path.insert`.** All test files must add
   `src/` to `sys.path` before importing from `operator_v7`:
   ```python
   sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
   from operator_v7 import Ticket, TicketStatus, TicketPriority
   ```

4. **Depth 2 (LEAF) is reserved / deprecated.** Do not assign tasks to
   depth=2 until NPU integration is re-enabled.

5. **The runner implements deadlock detection.** A ticket blocked with no
   runnable peers triggers a dependency graph printout and exits 1.

6. **Audit logs are append-only JSONL.** `logs/<id>-attempts.jsonl` must
   never be rewritten.

7. **Tool dispatch is now dynamic.** `parse_and_run_tools()` calls
   `REGISTRY.call(tool, args)` — not a hardcoded if/elif chain.
   `REGISTRY` is a module-level singleton in `agent/runner.py`.

8. **`run_command` is a registered tool.** It wraps `tools/terminal.run_command`
   and is available to any ticket via `TOOL: run_command`.

---

## Repository Owner

MrSnowNB. Hardware: RTX 6000 ADA workstation, Windows 11. Local inference
via Lemonade (primary) or Ollama. Python 3.10.11. pytest 7.4.3.

---

## Files You Will Touch Most

| File | Purpose |
|---|---|
| `src/operator_v7.py` | Ticket dataclass — the type layer |
| `src/ticket_io.py` | Typed ticket loader + as_dict() shim |
| `agent/runner.py` | Decompose + drain loop (REGISTRY-wired) |
| `tools/registry.py` | Dynamic tool registry |
| `tools/terminal.py` | subprocess wrapper + DANGEROUS_PATTERNS |
| `src/trajectory_extractor.py` | Step 4 target — reads attempt logs, writes skills/ |
| `tickets/template.yaml` | Ticket schema |
| `settings.yaml` | Model endpoint config |
| `tests/test_multistep_harness.py` | Primary regression gate |
| `logs/luffy-journal.jsonl` | Luffy Law audit trail |

---

## What You Must Not Do

- Do not create an `Operator` class
- Do not hardcode model names in `agent/runner.py`
- Do not rewrite `logs/*.jsonl` files
- Do not commit without writing a journal entry first
- Do not assign work to depth=2 (LEAF) until NPU integration is re-enabled
- Do not import from `src.operator_v7` with the `src.` prefix — use
  `sys.path.insert` and import `from operator_v7 import ...`
- Do not add tools to runner.py directly — register them via `REGISTRY.register()`

---

## How to Give Yourself More Context

```
AI-FIRST/ARCHITECTURE.md        — dataclass fields, ticket lifecycle, module inventory
AI-FIRST/NEXT-STEPS.md          — build queue, open work, entry points
AI-FIRST/STEP-04-TRAJECTORY.md  — active spec for Step 4
OPENCLAW-PLAN.md                — full Phase 3 specification
VISION.md                       — long-range project direction
TROUBLESHOOTING.md              — known failure modes and fixes
```
