# Fractal Claws — Next Steps (AI-FIRST)

> **AI-FIRST DOC** — This is the canonical build queue for coding agents.
> Each step has a status, a validation gate, and a link to its full spec.
> An agent should complete the gate before marking a step DONE.
> This file is vendor-agnostic: no model names, no endpoint URLs.

---

## How to Use This File

1. Read the current `[ ]` step
2. Read the linked `STEP-XX-*.md` spec in `AI-FIRST/`
3. **Apply first principles before touching any file:**
   - What invariant does this step preserve?
   - What is the current state of the system?
   - What is the minimal change that moves it forward?
4. Build the code
5. Run the validation gate: `pytest tests/ -v`
6. All tests green → **write journal entry first** → then `git commit`
7. Mark step `[x] DONE` → move to next step

---

## Luffy Law — Commit Protocol

> **Journal first. Always.**

Before every `git commit`:
1. `pytest tests/` — gate must be green
2. Append entry to `logs/luffy-journal.jsonl` (valid JSON + `\n`)
3. `git add <changed files> logs/luffy-journal.jsonl`
4. `git commit -m "STEP-XX: description"`
5. `git push`

**Journal integrity is a hard invariant.** A malformed line is a violation.
Detect it → split and correct (never rewrite) → then write the new entry.

### Journal Entry Schema (STEP-07+ — includes anchor)

```json
{
  "ts": "ISO-8601",
  "step": "STEP-XX-Y",
  "action": "...",
  "status": "done",
  "files": ["..."],
  "anchor": {
    "system_state": "<one sentence: what is true about the system right now>",
    "open_invariants": ["<invariant 1>", "<invariant 2>"],
    "next_entry_point": "<STEP-XX-Y: what to do next and which file to touch first>"
  }
}
```

The `anchor` field is the **cold-start signal** — a new agent session reads ONLY
the last journal line to reconstruct system state. No spec re-reads. No file loads.
The `next_entry_point` is the single source of truth for what to do next.

**Entries written before STEP-07 do not have `anchor` — this is expected.**
Do not backfill old entries. Write new entries with `anchor` from STEP-07-A onwards.

> **Known schema debt:** The STEP-07-F journal entry has `anchor` as a flat string
> rather than the required object. This is a known shortcut. The next journal entry
> (STEP-08) must use the full object schema. Do not backfill.

---

## HALT Protocol

If the human says HALT:
1. Stop all active work immediately
2. Write status to `TROUBLESHOOTING.md`
3. Append one journal entry
4. Stop — do not commit, do not fix anything else

Exception: journal integrity fix is permitted during HALT documentation.

---

## Build Queue

### [x] DONE — Step 1: Typed Ticket I/O Bridge
**Spec:** `AI-FIRST/STEP-01-TICKET-IO.md`  
**File:** `src/ticket_io.py`  
**Gate:** `pytest tests/test_ticket_io.py -v` ✅  
**What it does:** Bridges raw-dict YAML loading with the canonical `Ticket` dataclass.
Adds schema validation, enum coercion, status aliasing, and a backward-compatible
`as_dict()` shim for incremental migration.

---

### [x] DONE — Step 2: Terminal Tool + Tool Registry
**Spec:** `AI-FIRST/STEP-02-TERMINAL-REGISTRY.md`  
**Files:** `tools/terminal.py`, `tools/registry.py`  
**Gate:** `pytest tests/test_tools.py -v` ✅ 14/14  
**What it does:**
- `tools/terminal.py` — `subprocess.run` wrapper with `DANGEROUS_PATTERNS` denylist,
  sandbox enforcement, timeout. Windows-compatible (`_shell_cmd()` join for win32).
- `tools/registry.py` — dynamic tool dispatch via `TOOL_SCHEMA`. Replaces if/elif.

---

### [x] DONE — Step 3: Wire Registry into runner.py
**Spec:** `AI-FIRST/STEP-03-RUNNER-WIRING.md`  
**Files:** `agent/runner.py`, `tests/test_runner_dispatch.py`  
**Gate:** `pytest tests/test_runner_dispatch.py -v` ✅ 11/11  
**What it does:**
- `REGISTRY = ToolRegistry()` module-level singleton in runner.py
- `parse_and_run_tools()` calls `REGISTRY.call(tool, args)` — no more if/elif
- `run_command` registered as first-class tool

---

### [x] DONE — Step 4: Trajectory Extractor
**Spec:** `AI-FIRST/STEP-04-TRAJECTORY.md`  
**File:** `src/trajectory_extractor.py`  
**Gate:** `pytest tests/test_trajectory.py -v` ✅ 13/13  
**What it does:**
- Post-run pass: reads closed ticket attempt logs
- Identifies winning execution paths (outcome=pass chains)
- Extracts tool sequence, token count, elapsed time, goal class
- Writes `skills/<goal-class>.yaml` — executable memory for reuse

---

### [x] DONE — Step 5: Full Typed Field Migration of runner.py
**Spec:** `AI-FIRST/STEP-05-RUNNER-MIGRATION.md`  
**Files:** `agent/runner.py`, `src/operator_v7.py`, `tests/test_runner_dispatch.py`  
**Gate:** `pytest tests/ -v` ✅ 151 passed, 1 skipped, 0 failed  
**What it does:** All `ticket.get()`/`ticket[key]` replaced with typed `ticket.field` access.

---

### [x] DONE — Step 6: Skill-Aware Decomposition
**Spec:** `AI-FIRST/STEP-06-SKILL-DECOMP.md`  
**Files:** `agent/runner.py`, `src/skill_store.py`, `tests/test_skill_decomp.py`  
**Gate:** `pytest tests/ -v` ✅ 167 passed, 1 skipped, 0 failed  
**What it does:**
- `src/skill_store.py` — load/match/write skill YAML with fuzzy matching (edit-distance ≤ 2)
- Cache check in `execute_ticket()` before `call_model()` — cache hit skips LLM entirely
- Audit JSONL written on cache hit with `source: skill_cache`
- `match_goal_class()` → exact then fuzzy → `load_skill()` → run `tool_sequence` via REGISTRY

---

### [x] DONE — Step 7: Anchor Journal + TicketResult + Lint Gate + Delegate Spawn
**Spec:** `AI-FIRST/STEP-07-ANCHOR-SPAWN.md`  
**Files:** `src/operator_v7.py`, `src/ticket_io.py`, `agent/runner.py`, `tools/delegate_task.py`,
`AI-FIRST/AGENT-PERSONA.md`, `tests/test_ticket_io.py`, `tests/integration/test_delegate_task.py`  
**Gate:** `pytest tests/ -v` ✅ 167 passed, 1 skipped, 0 failed  

**What was built (sub-tickets completed in order):**

| Ticket | Task | Status |
|---|---|---|
| STEP-07-A | Journal anchor schema + cold-start rule in AGENT-PERSONA.md | ✅ |
| STEP-07-B | `TicketResult` dataclass in `operator_v7.py`; migrate `ticket.result` | ✅ |
| STEP-07-C | `lint_ticket()` in `ticket_io.py`; warn on violation; log to `lint-violations.jsonl` | ✅ |
| STEP-07-D | `tools/delegate_task.py` — shared-filesystem transport; register in REGISTRY | ✅ |
| STEP-07-E | Integration test (`tests/integration/`) — skipped by default, manual ZBook run | ✅ |
| STEP-07-F | Gate (167/1/0), journal entry, commit f10a53a, push | ✅ |

**Known schema debt:** STEP-07-F journal entry has `anchor` as a flat string instead
of the spec object. STEP-08 journal entry must use the full object. Do not backfill.

---

### [ ] Step 8: Lint Hard-Fail + Multi-Ticket Chain  ← **NEXT**
**Spec:** (to be written: `AI-FIRST/STEP-08-LINT-CHAIN.md`)  
**Files:** `src/ticket_io.py`, `agent/runner.py`, `tests/test_ticket_io.py`  
**Gate:** `pytest tests/ -v` green after hard-fail promotion + chain test

**Tickets (in order):**
| Ticket | Task |
|---|---|
| STEP-08-A | Audit lint false-positive rate from real runs → promote warn → hard-fail in `lint_ticket()` |
| STEP-08-B | Multi-ticket dependency chain with `delegate_task` — parent chains child tickets |
| STEP-08-C | Deadlock detection across spawned children |
| STEP-08-D | Gate, journal (with full anchor object), commit, push |

**Prerequisite:** STEP-07 complete. ✅ Real ZBook integration test run with model loaded
required before promoting lint to hard-fail — measure false-positive rate first.

**First principles rationale:** The lint gate was purposely warn-not-block in Step 7
because the A3B child running cold might succeed even with a lint violation.
After real-run data, we have the evidence to hard-fail with confidence.
Multi-ticket chaining is the next level of the parent↔child protocol —
Key-Brain fires a chain of dependent tickets and Fractal Claws manages ordering
and result propagation.

---

### [ ] Step 9: Graphify — Knowledge Graph Navigation Index (Preview — Do Not Build Yet)
**What it does:**
- `tools/graphify.py` — AST walker builds `graph/fractal-claws.json`
- `query_graph` tool in REGISTRY — replaces speculative file reads
- Nodes: FILE, FUNCTION, CLASS, TICKET, SKILL, STEP. Edges: CALLS, IMPORTS, MODIFIES, DEPENDS_ON.
- Runs on commit (pre-commit hook or CI)

**Prerequisite:** STEP-08 complete. Repo must have ≥20 Python files for graph to be useful.

---

## Architecture Context

```
Layer 1: CLINE (Key-Brain / Orchestrator)  — 80B coder
  Reads anchor from last journal line (cold start: 1 line only)
  Reads skills/ → skips decomposition if goal class known
  Writes YAML tickets → lint_ticket() pre-flight
  Calls delegate_task() → sleeps while child executes
  Reads TicketResult.anchor → continues chain or escalates

Layer 2: FRACTAL CLAWS (Ticket Router / Gate)  ← this repo
  Dependency graph → drain loop → deadlock detect
  Typed Ticket + TicketResult contract (ticket_io + operator_v7)
  Tool registry (REGISTRY) → dispatches to execution layer
  Trajectory extractor → writes skills/ after each pass
  Skill store → reads skills/ before decomposition
  Lint gate → warns on malformed tickets before dispatch

Layer 3: OPENCLAW (Child Executor)  — A3B model
  Spawned by delegate_task() — loads only context_files from ticket
  Executes tool_sequence via REGISTRY
  Writes TicketResult to result_path (including anchor summary)
  Exits — parent reads result, continues

Layer 4: HERMES-STYLE TOOLS (Execution Layer)
  terminal, process, patch, search_files
  delegate_task (substrate abstraction)
  Every CLI binary on the machine

Substrate (ZBook POC → Liberty Mesh):
  ZBook:        shared filesystem (tickets/open/, tickets/closed/)
  Liberty Mesh: LoRa serial — Ticket.to_dict() → JSON → radio → JSON → Ticket.from_dict()
  Only tools/delegate_task.py changes per substrate
```

---

## Reproducibility Requirement

Every step must be completable on any machine with:
- Python 3.10+
- `pip install pyyaml pytest`
- No model, no endpoint, no API key required for tests
- No network access required for tests

Integration tests go in `tests/integration/` and are ALWAYS skipped by default.
Run manually: `pytest tests/integration/ -v -s --no-header`
