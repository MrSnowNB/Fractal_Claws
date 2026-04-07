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
5. All tests green → mark step `[x] DONE` → move to next step

---

## Build Queue

### [x] DONE — Step 1: Typed Ticket I/O Bridge
**Spec:** `AI-FIRST/STEP-01-TICKET-IO.md`  
**File:** `src/ticket_io.py`  
**Gate:** `python -m pytest tests/test_ticket_io.py -v`  
**What it does:** Bridges raw-dict YAML loading in runner.py with the canonical  
`Ticket` dataclass in operator_v7.py. Adds schema validation, enum coercion,  
status aliasing, and a backward-compatible `as_dict()` shim for incremental migration.  

---

### [ ] Step 2: Terminal Tool + Tool Registry
**Spec:** `AI-FIRST/STEP-02-TERMINAL-REGISTRY.md` *(to be written)*  
**Files:** `tools/terminal.py`, `tools/registry.py`  
**Gate:** `python -m pytest tests/test_tools.py -v` *(to be written)*  
**What it does:**  
- `tools/terminal.py` — wraps `subprocess.run` with a `TOOL_SCHEMA` dict,
  `DANGEROUS_PATTERNS` denylist, sandbox path enforcement, and timeout.
  Gives the agent shell access to any CLI binary on the machine.
- `tools/registry.py` — maps tool name strings to callables + validates args
  against `TOOL_SCHEMA`. Replaces the hardcoded `if tool == "read_file"` dispatch
  in runner.py with a dynamic registry.

**Unlock:** Once this step is complete, the agent can call `nmap`, `git`,
`meshtastic`, `gpg`, `ffmpeg`, and any other installed binary as a ticket action.

---

### [ ] Step 3: Wire Registry into runner.py
**Spec:** `AI-FIRST/STEP-03-RUNNER-WIRING.md` *(to be written)*  
**File:** `agent/runner.py` (refactor)  
**Gate:** `python -m pytest tests/test_runner_dispatch.py -v` *(to be written)*  
**What it does:**  
- Replaces hardcoded `if/elif tool ==` dispatch in `parse_and_run_tools()`
  with `registry.call(name, args)`
- Replaces raw `load_ticket` / `save_ticket` calls with `ticket_io` versions
  (Phase A migration: `as_dict()` shim, zero breakage)
- All existing runner tests must still pass

---

### [ ] Step 4: Trajectory Extractor
**Spec:** `AI-FIRST/STEP-04-TRAJECTORY.md` *(to be written)*  
**File:** `src/trajectory_extractor.py`  
**Gate:** `python -m pytest tests/test_trajectory.py -v` *(to be written)*  
**What it does:**  
- Post-run pass: reads `logs/<ticket_id>-attempts.jsonl`
- Identifies winning execution paths (outcome=pass chains)
- Writes `skills/<goal-class>.yaml` with the compressed toolpath
- This is the self-improving loop: Cline reads prior skills before decomposing,
  skipping re-decomposition of known-good goal classes

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
  Evaluates results → escalates or closes

Layer 2: FRACTAL CLAWS (Ticket Router / Gate)  ← this repo
  Dependency graph → drain loop → deadlock detect
  Typed Ticket contract (ticket_io) → audit JSONL
  Tool registry → dispatches to execution layer

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
