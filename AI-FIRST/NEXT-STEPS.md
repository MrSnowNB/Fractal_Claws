# Fractal Claws — Next Steps (AI-FIRST)

> **AI-FIRST DOC** — This is the canonical build queue for coding agents.
> Each step has a status, a validation gate, and a link to its full spec.
> An agent should complete the gate before marking a step DONE.
> This file is vendor-agnostic: no model names, no endpoint URLs.

---

## How to Use This File

1. Read the current `[ ]` step
2. Read the linked `STEP-XX-*.md` spec in `AI-FIRST/`
3. Build the code
4. Run the validation gate: `python -m pytest tests/test_<module>.py -v`
5. All tests green → **write journal entry first** → then `git commit`
6. Mark step `[x] DONE` → move to next step

---

## Luffy Law — Commit Protocol

> **Journal first. Always.**
>
> Before every `git commit`, append a JSONL entry to `logs/luffy-journal.jsonl`,
> then stage it with the rest of the commit. Never push without the journal entry.
>
> Entry schema:
> ```json
> {"ts": "ISO-8601", "step": "STEP-XX-Y", "action": "...", "status": "done", "files": [...]}
> ```
>
> Commit order:
> 1. `python -m pytest` — gate must be green
> 2. Append journal entry to `logs/luffy-journal.jsonl`
> 3. `git add <changed files> logs/luffy-journal.jsonl`
> 4. `git commit -m "STEP-XX: description"`
> 5. `git push`

---

## Build Queue

### [x] DONE — Step 1: Typed Ticket I/O Bridge
**Spec:** `AI-FIRST/STEP-01-TICKET-IO.md`  
**File:** `src/ticket_io.py`  
**Gate:** `python -m pytest tests/test_ticket_io.py -v`  
**What it does:** Bridges raw-dict YAML loading in runner.py with the canonical
`Ticket` dataclass. Adds schema validation, enum coercion, status aliasing,
and a backward-compatible `as_dict()` shim for incremental migration.

---

### [x] DONE — Step 2: Terminal Tool + Tool Registry
**Spec:** `AI-FIRST/STEP-02-TERMINAL-REGISTRY.md`  
**Files:** `tools/terminal.py`, `tools/registry.py`  
**Gate:** `python -m pytest tests/test_tools.py -v` — 14/14 pass  
**What it does:**
- `tools/terminal.py` — wraps `subprocess.run` with `DANGEROUS_PATTERNS` denylist,
  sandbox path enforcement, and timeout. Windows-compatible (`shell=True`).
- `tools/registry.py` — maps tool name strings to callables + validates args
  against `TOOL_SCHEMA`. Dynamic dispatch replaces hardcoded if/elif.

---

### [x] DONE — Step 3: Wire Registry into runner.py
**Spec:** `AI-FIRST/STEP-03-RUNNER-WIRING.md`  
**Files:** `agent/runner.py` (refactor), `tests/test_runner_dispatch.py` (new)  
**Gate:** `python -m pytest tests/test_runner_dispatch.py -v` — 11/11 pass  
**What it does:**
- `REGISTRY = ToolRegistry()` module-level singleton in runner.py
- `parse_and_run_tools()` calls `REGISTRY.call(tool, args)` — no more if/elif
- `run_command` registered as first-class tool
- Gate ticket (STEP-03-C) enforced journal-first commit protocol

---

### [ ] Step 4: Trajectory Extractor
**Spec:** `AI-FIRST/STEP-04-TRAJECTORY.md`  
**File:** `src/trajectory_extractor.py`  
**Gate:** `python -m pytest tests/test_trajectory.py -v` *(to be written by Luffy)*  
**Tickets:** `tickets/open/STEP-04-A.yaml`, `STEP-04-B.yaml`, `STEP-04-C.yaml`  
**What it does:**
- Post-run pass: reads `logs/<ticket_id>-attempts.jsonl` for all closed tickets
- Identifies winning execution paths (outcome=pass chains)
- Extracts the tool sequence, token count, elapsed time, and goal class
- Writes `skills/<goal-class>.yaml` — compressed toolpath for reuse
- Self-improving loop: Cline reads prior skills before decomposing,
  skipping re-decomposition of known-good goal classes

**Unlock:** Once this step is complete, the runner has memory of what worked.
New goals that match a known skill class skip decomposition entirely and
run the winning toolpath directly.

---

### [ ] Step 5: Full Phase A Migration of runner.py
**Spec:** `AI-FIRST/STEP-05-RUNNER-MIGRATION.md` *(to be written)*  
**File:** `agent/runner.py` (full typed field access)  
**Gate:** Full existing test suite passes + new typed-access tests  
**What it does:**
- Migrates all `ticket.get("field")` call-sites to `ticket.field` attribute access
- Removes `as_dict()` shim usage
- `load_ticket()` in runner now returns `Ticket` directly (Phase C migration)

---

## Architecture Context

The three-layer stack this build queue produces:

```
Layer 1: CLINE (Key-Brain / Orchestrator)
  Reads goal → decomposes → writes YAML tickets
  Reads skills/ before decomposing — skips known-good goal classes
  Evaluates results → escalates or closes

Layer 2: FRACTAL CLAWS (Ticket Router / Gate)  ← this repo
  Dependency graph → drain loop → deadlock detect
  Typed Ticket contract (ticket_io) → audit JSONL
  Tool registry (REGISTRY) → dispatches to execution layer
  Trajectory extractor → writes skills/ after each pass

Layer 3: HERMES-STYLE TOOLS (Execution Layer)
  terminal, process, patch, search_files
  web_search, vision, delegate_task, cronjob
  Every CLI binary on the machine
```

## Reproducibility Requirement

Every step must be completable on any machine with:
- Python 3.10+
- `pip install pyyaml pytest`
- No model, no endpoint, no API key required for tests
- No network access required for tests

Integration tests (requiring a live model endpoint) go in `tests/integration/`
and are always skipped by default (`pytest -m 'not integration'`).
