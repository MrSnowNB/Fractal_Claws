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

Entry schema:
```json
{"ts": "ISO-8601", "step": "STEP-XX-Y", "action": "...", "status": "done", "files": [...]}
```

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
  sandbox enforcement, timeout. Windows-compatible.
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
- Cline reads `skills/` before decomposing — skips known-good goal classes

**Unlock:** Runner now has memory of what worked. Matching goal classes skip
decomposition and run the winning toolpath directly.

---

### [x] DONE — Step 5: Full Typed Field Migration of runner.py
**Spec:** `AI-FIRST/STEP-05-RUNNER-MIGRATION.md`  
**Files:** `agent/runner.py`, `src/operator_v7.py`, `tests/test_runner_dispatch.py`  
**Gate:** `pytest tests/ -v` ✅ 151 passed, 1 skipped, 0 failed  
**Dict-access call sites removed:** all (`grep 'ticket\.get\|ticket\['` → zero hits)  
**What it does:**
- `load_ticket()` now returns a typed `Ticket` dataclass (via `ticket_io.load_ticket()`)
- All `ticket.get("field")` and `ticket["field"]` call sites replaced with `ticket.field`
- Optional fields (`depends_on`, `context_files`, `result_path`, `task`) added to dataclass
- `as_dict()` shim kept in `ticket_io.py` for serialization only — removed from runner read paths
- `ticket.id` confirmed as canonical attribute; `from_dict()` maps `ticket_id` → `id`

---

### [ ] Step 6: Skill-Aware Decomposition  ← ACTIVE
**Spec:** `AI-FIRST/STEP-06-SKILL-DECOMP.md`  
**Files:** `agent/runner.py`, `src/skill_store.py`, `tests/test_skill_decomp.py`  
**Gate:** `pytest tests/ -v` all green + skill cache hit path exercised by E2E test  

**Tickets (in order):**
| Ticket | Task | Depends on |
|---|---|---|
| STEP-06-A | Write `src/skill_store.py` — load/match/write skill YAML | — |
| STEP-06-B | Wire `skill_store` into runner decomposition path | STEP-06-A |
| STEP-06-C | Write `tests/test_skill_decomp.py` — unit + E2E cache-hit test | STEP-06-B |
| STEP-06-D | Gate, journal, commit, push | STEP-06-C |

**First principles rationale:**  
The trajectory extractor (Step 4) writes `skills/<goal-class>.yaml` after every
successful run. Those files are executable memory — but nothing reads them yet.
This step closes the loop: before decomposing a goal, the runner checks `skills/`
for a matching goal class. A hit skips LLM decomposition entirely and runs the
cached toolpath directly. A miss falls through to normal decomposition and writes
a new skill on success.

**What to watch for:**
- Goal-class matching must be exact-string then fuzzy (edit-distance ≤ 2)
- Skill YAML must survive a round-trip through `skill_store.load()` → `skill_store.write()`
- Cache hit must be logged to audit JSONL with `source: skill_cache`
- E2E test must write a real skill file, trigger runner, and assert decompose was NOT called

---

### [ ] Step 7: Typed TicketResult + OpenClaw Spawn (Preview — Do Not Build Yet)
**What it does:**
- `ticket.result` raw dict replaced with typed `TicketResult` dataclass
- `delegate_task` tool triggers a real child runner process on second GPU at depth=1
- Foundation for multi-agent coordination (Key-Brain ↔ OpenClaw)

**Prerequisite:** Step 6 complete. Skill-aware routing must be stable before
adding child-process complexity.

---

## Architecture Context

```
Layer 1: CLINE (Key-Brain / Orchestrator)
  Reads goal → reads skills/ → skips decomposition if goal class known
  Writes YAML tickets → evaluates results → escalates or closes

Layer 2: FRACTAL CLAWS (Ticket Router / Gate)  ← this repo
  Dependency graph → drain loop → deadlock detect
  Typed Ticket contract (ticket_io + operator_v7) → audit JSONL
  Tool registry (REGISTRY) → dispatches to execution layer
  Trajectory extractor → writes skills/ after each pass
  Skill store → reads skills/ before decomposition (Step 6)

Layer 3: HERMES-STYLE TOOLS (Execution Layer)
  terminal, process, patch, search_files
  web_search, vision, delegate_task, cronjob
  Every CLI binary on the machine
```

---

## Reproducibility Requirement

Every step must be completable on any machine with:
- Python 3.10+
- `pip install pyyaml pytest`
- No model, no endpoint, no API key required for tests
- No network access required for tests

Integration tests go in `tests/integration/` and are always skipped by default.
