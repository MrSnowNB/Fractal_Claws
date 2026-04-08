# Fractal Claws — AI Onboarding Context

> **Read this file first.** It gives you everything you need to understand what
> this system does, where it is right now, and what rules you must follow.
> After reading this file, read `AI-FIRST/AGENT-PERSONA.md` then
> `AI-FIRST/ARCHITECTURE.md` then `AI-FIRST/NEXT-STEPS.md`.

---

## How to Use This Folder

This folder is the system’s self-description. It is written to be machine-actionable,
not just human-readable. An agent that reads it can:

- Understand the current validated state without asking
- Identify what invariants must be true
- Find the gap between current state and required state
- Choose the minimal correct intervention

**Reading this folder is not optional context-loading. It is calibration.**
Do not act until you have read it.

---

## What This System Is

Fractal Claws is a **local agentic harness** for running multi-step AI tasks
without cloud infrastructure. A parent agent (Cline in VS Code) decomposes a
human goal into discrete tickets. A child runner (`agent/runner.py`) picks up
those tickets, executes tool calls, writes results, and closes the tickets.
Everything runs on local hardware via an OpenAI-compatible endpoint.

**The core loop:**
```
Human gives goal
  → parent reads skills/ — skips decomposition if goal class known
  → parent decomposes into tickets/open/*.yaml
  → runner picks up tickets in dependency order
  → runner calls tools via REGISTRY.call() (dynamic dispatch)
  → runner writes result to logs/<id>-result.txt
  → runner closes ticket to tickets/closed/<id>.yaml
  → trajectory extractor reads closed tickets → writes skills/
  → parent reads result, continues or escalates
```

---

## First Principles — How to Reason in This System

Before acting on any ticket or instruction, ask:

1. **What invariant does this system require?**
   Read the docs. The invariants are stated explicitly:
   - Tests must be green before commit
   - Journal must be valid JSONL before every push
   - Audit logs are append-only and never rewritten
   - Tickets declare dependencies and cannot run out of order

2. **What is the actual current state?**
   Read the filesystem. Read the logs. Read the journal.
   Do not assume state from context. Verify it.

3. **What is the minimal intervention that restores invariant?**
   Not the most complete solution. The smallest correct one.
   Fix the line. Don’t rebuild the system.

**If an instruction conflicts with an invariant, honor the invariant.**
**Document why. Then act.**

---

## Current Validated State (Gate: 2026-04-07)

| Step | What was built | Gate |
|---|---|---|
| Step 1 | `src/ticket_io.py` — typed Ticket loader + `as_dict()` shim | `pytest tests/test_ticket_io.py` ✅ |
| Step 2 | `tools/terminal.py` + `tools/registry.py` | `pytest tests/test_tools.py` ✅ 14/14 |
| Step 3 | Registry wired into `agent/runner.py` | `pytest tests/test_runner_dispatch.py` ✅ 11/11 |
| Step 4 | `src/trajectory_extractor.py` + `skills/` populated | `pytest tests/test_trajectory.py` ✅ 13/13 |
| Step 5 | Full typed field migration of runner.py | `pytest tests/` — **next** |

**Do not refactor the `Ticket` dataclass or the ticket lifecycle without running
the full gate (`pytest tests/ -v`) first.**

---

## Luffy Law — Commit Protocol (MANDATORY)

> **Journal first. Always. No exceptions.**

Before every `git commit`:
1. `pytest tests/` — all green
2. Append entry to `logs/luffy-journal.jsonl`
3. `git add <files> logs/luffy-journal.jsonl`
4. `git commit`
5. `git push`

**Journal integrity is a hard invariant:**
- Every line must be valid JSON terminated by `\n`
- A malformed or concatenated line is a protocol violation
- Detect it → fix it (split, do not rewrite) → then write the new entry
- Never push with a corrupt journal

Entry schema:
```json
{"ts": "ISO-8601", "step": "STEP-XX-Y", "action": "...", "status": "done", "files": [...]}
```

---

## HALT Protocol

When the human says HALT:
1. Stop all active work immediately
2. Write current status to `TROUBLESHOOTING.md`
3. Append one journal entry documenting the halt
4. Stop completely — do not commit, do not fix anything else

Exception: journal integrity fix is permitted during HALT documentation
because it is required to write a valid journal entry. Fix it, then stop.

---

## Critical Facts (Do Not Get These Wrong)

1. **There is no `Operator` class.** `src/operator_v7.py` defines `Ticket`,
   `TicketStatus`, `TicketPriority`, `TicketDepth` only.

2. **Runtime tickets are gitignored.** `tickets/open/*.yaml` and
   `tickets/in_progress/*.yaml` do not live in the repo.

3. **Import pattern requires `sys.path.insert`.** All test files must add
   `src/` to `sys.path` before importing from `operator_v7`.

4. **Depth 2 (LEAF) is reserved / deprecated.** Do not assign tasks to
   depth=2 until NPU integration is re-enabled.

5. **The runner implements deadlock detection.** A ticket blocked with no
   runnable peers triggers a dependency graph printout and exits 1.

6. **Audit logs are append-only JSONL.** `logs/<id>-attempts.jsonl` must
   never be rewritten.

7. **Tool dispatch is dynamic.** `parse_and_run_tools()` calls
   `REGISTRY.call(tool, args)` — not a hardcoded if/elif chain.

8. **`run_command` is a registered tool.** Wraps `tools/terminal.run_command`.

9. **`skills/` is executable memory.** Not just data — structured so any
   agent instance can read a skill file and reconstruct the execution plan.
   Cline reads `skills/` before decomposing to skip known-good goal classes.

10. **The AI-FIRST folder is the ground truth.** When in doubt, read it.
    An agent that reads it can audit the system state without asking.

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
| `src/trajectory_extractor.py` | Post-run pass → writes skills/ |
| `skills/` | Executable memory — winning toolpaths by goal class |
| `tickets/template.yaml` | Ticket schema |
| `settings.yaml` | Model endpoint config |
| `tests/test_multistep_harness.py` | Primary regression gate |
| `logs/luffy-journal.jsonl` | Luffy Law audit trail |

---

## What You Must Not Do

- Do not create an `Operator` class
- Do not hardcode model names in `agent/runner.py`
- Do not rewrite `logs/*.jsonl` files — split and correct only
- Do not commit without writing a journal entry first
- Do not assign work to depth=2 (LEAF) until NPU integration is re-enabled
- Do not import from `src.operator_v7` with the `src.` prefix
- Do not add tools to runner.py directly — register via `REGISTRY.register()`
- Do not ignore a HALT instruction — stop work immediately
- Do not act on a ticket without reading this folder first

---

## How to Give Yourself More Context

```
AI-FIRST/AGENT-PERSONA.md       — who Luffy is, first principles, HALT protocol, Luffy Law
AI-FIRST/ARCHITECTURE.md        — dataclass fields, ticket lifecycle, module inventory
AI-FIRST/NEXT-STEPS.md          — build queue, open work, entry points
AI-FIRST/STEP-04-TRAJECTORY.md  — completed spec for Step 4
OPENCLAW-PLAN.md                — full Phase 3 specification
VISION.md                       — long-range project direction
TROUBLESHOOTING.md              — known failure modes and fixes
```
