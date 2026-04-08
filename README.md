---
title: Fractal Claws — Self-Healing Recursive Agent Harness
version: "7.0"
gate: "step-7-validated — 2026-04-08"
---

# Fractal Claws

A local agentic harness where a **parent agent** (Key-Brain: 80B coder in Cline)
decomposes a goal into typed tickets and dispatches them to a **child runner**
(OpenClaw: A3B model). Tickets are substrate-agnostic messages — they travel
over shared filesystem today, LoRa radio tomorrow.

The system improves over time: after every passing run, a trajectory extractor
writes `skills/<goal-class>.yaml`. The next matching goal skips LLM decomposition
entirely and runs the cached toolpath directly.

**One harness. Two roles. Executable memory. No cloud. Any substrate.**

> **Current gate (2026-04-08):** Steps 1–7 complete and validated.  
> `pytest tests/ -v` → 167 passed, 1 skipped, 0 failed.  
> Step 8 (Lint Hard-Fail + Multi-Ticket Chain) is next.

---

## Architecture

```
Key-Brain (80B, Cline)          OpenClaw (A3B, child runner)
  reads anchor from journal  →    loads only context_files
  reads skills/ (cache hit?)  →    executes tool_sequence via REGISTRY
  lint_ticket() pre-flight    →    writes TicketResult to result_path
  delegate_task() dispatch    ←    exits — parent reads TicketResult.anchor
        ↓
   sleeps (frees RAM for child)
```

### Ticket as Message

A ticket is not a file. It is a **typed message** (`Ticket.to_dict()` → JSON)
that can travel over any substrate:

| Substrate | Transport | Notes |
|---|---|---|
| Shared filesystem | `tickets/open/*.yaml` | ZBook POC (current) |
| TCP socket | JSON over localhost | Same machine, isolated processes |
| LoRa serial | Compact JSON over radio | Liberty Mesh deployment |
| MQTT | JSON to broker topic | Multi-node mesh |

Only `tools/delegate_task.py` changes per substrate. The ticket schema, runner
logic, and tool registry are substrate-agnostic.

---

## How It Works

```
Human gives goal
  → Key-Brain reads anchor (last journal line) — single cold-start read
  → Key-Brain reads skills/ — skips decomposition if goal class known
  → Key-Brain decomposes → lint_ticket() pre-flight → writes tickets/open/*.yaml
  → delegate_task() dispatches ticket → Key-Brain sleeps (frees RAM)
  → OpenClaw wakes → loads context_files only → executes via REGISTRY
  → OpenClaw writes TicketResult (with anchor) → exits
  → Key-Brain wakes → reads TicketResult.anchor → no file re-reads
  → trajectory extractor writes skills/ on pass
  → Key-Brain continues chain or escalates
```

---

## Step 7 — What Was Built

Step 7 completed the four pillars of the parent↔child dispatch loop:

### A — Anchor Journal
Every journal entry now carries an `anchor` object with three fields:
- `system_state` — one sentence: what is true about the system right now
- `open_invariants` — list of invariants that must remain true
- `next_entry_point` — exactly what to do next and which file to touch first

On cold start, Key-Brain reads **one line** — the last journal entry — and knows
full system state. No spec re-reads, no file scans before the first ticket.

### B — TicketResult Dataclass
`TicketResult` lives in `src/operator_v7.py`. It is the typed return contract
from child to parent: outcome, elapsed_s, tokens, tool_calls, artifact_paths,
reason, and anchor. `ticket.result` migrated from `Dict` → `Optional[TicketResult]`.
Backward compatible — old YAML files with no `result` field default to `None`.

### C — Lint Gate
`lint_ticket()` in `src/ticket_io.py` is the pre-flight check before any ticket
leaves the parent's memory domain. Four rules:
- LINT-001: task references `.py` file but `context_files` is empty
- LINT-002: `produces`/`consumes` declared but `context_files` empty
- LINT-003: `context_files` entry does not exist on disk
- LINT-004: `task` is empty

Violations warn (not block) and write to `logs/lint-violations.jsonl`.
Hard-fail promotion comes in Step 8 after false-positive audit.

### D — delegate_task Transport Layer
`tools/delegate_task.py` is the **only** place transport logic lives.
Currently: write ticket to `tickets/open/`, poll `tickets/closed/` for result.
To swap substrate (e.g. LoRa serial): replace ~20 lines in this file only.
The `Ticket.to_dict()` / `TicketResult.from_dict()` contract does not change.

### E/F — Integration Test + Gate
Integration tests live in `tests/integration/test_delegate_task.py`.
Skipped by default in all automated runs. Run manually on ZBook with model loaded:
`pytest tests/integration/ -v -s`

---

## Components

| Component | File | What it does |
|---|---|---|
| **Key-Brain** | Cline (VS Code) | Orchestrates via `.clinerules/`; writes + dispatches tickets |
| **Runner** | `agent/runner.py` | Decompose → drain → execute → close |
| **Ticket** | `src/operator_v7.py:Ticket` | Typed message dataclass; substrate-agnostic |
| **TicketResult** | `src/operator_v7.py:TicketResult` | Typed return from child; includes anchor |
| **Registry** | `tools/registry.py` | Dynamic tool dispatch; no hardcoded if/elif |
| **Terminal** | `tools/terminal.py` | subprocess wrapper; DANGEROUS_PATTERNS denylist; win32-safe |
| **Ticket I/O** | `src/ticket_io.py` | Typed YAML loader + lint_ticket() pre-flight |
| **Skill Store** | `src/skill_store.py` | load/match/write skill YAML; fuzzy matching (edit-dist ≤ 2) |
| **Trajectory** | `src/trajectory_extractor.py` | Reads closed tickets → writes skills/ |
| **Delegate** | `tools/delegate_task.py` | Substrate abstraction layer — swap for LoRa in ~20 lines |
| **Skills** | `skills/<goal-class>.yaml` | Executable memory: winning toolpaths by goal class |
| **Audit log** | `logs/<id>-attempts.jsonl` | Append-only; one JSON record per attempt |
| **Journal** | `logs/luffy-journal.jsonl` | Luffy Law audit trail; anchor field from Step 7 |
| **Lint log** | `logs/lint-violations.jsonl` | Warnings from lint_ticket() — review before dispatch |

---

## Build Progress

| Step | What | Gate | Status |
|---|---|---|---|
| 1 | Typed Ticket I/O Bridge | `pytest tests/test_ticket_io.py` | ✅ DONE |
| 2 | Terminal Tool + Tool Registry | `pytest tests/test_tools.py` 14/14 | ✅ DONE |
| 3 | Wire Registry into runner.py | `pytest tests/test_runner_dispatch.py` 11/11 | ✅ DONE |
| 4 | Trajectory Extractor + skills/ | `pytest tests/test_trajectory.py` 13/13 | ✅ DONE |
| 5 | Full Typed Field Migration | `pytest tests/ -v` + zero grep hits | ✅ DONE |
| 6 | Skill-Aware Decomposition | `pytest tests/ -v` 167 passed | ✅ DONE |
| 7 | Anchor + TicketResult + Lint + Delegate | `pytest tests/ -v` 167 passed, 1 skipped | ✅ DONE |
| 8 | Lint Hard-Fail + Multi-Ticket Chain | TBD | ⏳ NEXT |
| 9 | Graphify — Knowledge Graph Index | TBD | ⏳ Queued |

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/MrSnowNB/Fractal_Claws.git
cd Fractal_Claws

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your endpoint
#    Edit settings.yaml: set model.id and model.endpoint

# 4. Run pre-flight check
python pre_flight.py

# 5. Decompose a goal and drain the ticket queue
python agent/runner.py --goal "<your goal here>"

# 6. Or place a ticket manually and run once
cp tickets/template.yaml tickets/open/TASK-001.yaml
# Edit TASK-001.yaml: fill ticket_id, task, context_files, result_path
python agent/runner.py --once

# 7. Run the full regression gate
pytest tests/ -v

# 8. Manual integration test (requires model loaded)
pytest tests/integration/ -v -s --no-header
```

---

## Luffy Law — Commit Protocol

Before every `git commit`, the coding agent must:

1. `pytest tests/` — all green
2. Append a JSONL entry to `logs/luffy-journal.jsonl` — **with `anchor` field (STEP-07+)**
3. `git add <changed files> logs/luffy-journal.jsonl`
4. `git commit -m "STEP-XX: description"`
5. `git push`

Journal entry schema (STEP-07+):
```json
{
  "ts": "ISO-8601",
  "step": "STEP-XX-Y",
  "action": "...",
  "status": "done",
  "files": [...],
  "anchor": {
    "system_state": "one sentence — what is true about the system right now",
    "open_invariants": ["..."],
    "next_entry_point": "STEP-XX-Y: what to do next and which file to touch first"
  }
}
```

> **Note:** The STEP-07-F journal entry has `anchor` as a flat string (legacy format).
> All entries from STEP-08 onward must use the full anchor object schema above.

---

## First Principles

Fractal Claws agents reason from invariants, not just instructions:

1. **What invariant must be true?** (green tests, valid journal, typed contract, dep order)
2. **What is the actual current state?** (read the filesystem, verify — do not assume)
3. **What is the minimal intervention?** (fix the line, add the field, don't rebuild)

The `AI-FIRST/` folder is the system's self-description. An agent that reads it
can audit state, find violations, and self-correct — without asking.

---

## Repo Structure

```
Fractal_Claws/
├── AI-FIRST/                    ← Start here if you are a new AI assistant
│   ├── CONTEXT.md               ← System overview + current state (read first)
│   ├── AGENT-PERSONA.md         ← Luffy: first principles, cold-start rule, Luffy Law
│   ├── ARCHITECTURE.md          ← Dataclass map, ticket lifecycle, module inventory
│   ├── NEXT-STEPS.md            ← Build queue and open work
│   ├── KNOWN-ISSUE-context-window.md  ← Context bottleneck diagnosis + solution trajectory
│   ├── STEP-01-TICKET-IO.md
│   ├── STEP-02-TERMINAL-REGISTRY.md
│   ├── STEP-03-RUNNER-WIRING.md
│   ├── STEP-04-TRAJECTORY.md
│   ├── STEP-05-RUNNER-MIGRATION.md
│   ├── STEP-06-SKILL-DECOMP.md
│   └── STEP-07-ANCHOR-SPAWN.md  ← Complete — kept for reference
├── .clinerules/                 ← Cline rule files (parent config)
├── agent/
│   └── runner.py                ← Decompose + drain + skill cache + delegate dispatch
├── src/
│   ├── operator_v7.py           ← Ticket, TicketResult, TicketStatus, TicketPriority
│   ├── ticket_io.py             ← Typed YAML loader + lint_ticket() pre-flight
│   ├── skill_store.py           ← load/match/write skill YAML (Step 6 ✅)
│   └── trajectory_extractor.py  ← Post-run pass → writes skills/ (Step 4 ✅)
├── tickets/
│   ├── template.yaml
│   ├── open/
│   ├── in_progress/
│   ├── closed/
│   └── failed/
├── tools/
│   ├── registry.py              ← Dynamic tool registry (Step 2 ✅)
│   ├── terminal.py              ← subprocess wrapper + denylist; win32-safe (Step 2 ✅)
│   ├── delegate_task.py         ← Substrate abstraction — dispatch to child (Step 7 ✅)
│   ├── read_file.py
│   └── write_file.py
├── tests/
│   ├── integration/             ← Manual-only tests (always skipped in CI)
│   │   └── test_delegate_task.py
│   ├── conftest.py
│   ├── test_multistep_harness.py
│   ├── test_ticket_io.py
│   ├── test_tools.py
│   ├── test_runner_dispatch.py
│   ├── test_trajectory.py
│   └── test_skill_decomp.py     ← Step 6 ✅
├── logs/
│   ├── luffy-journal.jsonl      ← Luffy Law audit trail (anchor field from Step 7)
│   ├── lint-violations.jsonl    ← lint_ticket() warnings (created on first violation)
│   └── <id>-attempts.jsonl      ← Per-ticket attempt logs (append-only)
├── skills/                      ← Executable memory: winning toolpaths by goal class
├── output/                      ← exec_python sandbox
├── settings.yaml
├── pre_flight.py
└── requirements.txt
```

---

## Validation Gates

| Gate | Command | Status |
|---|---|---|
| Step 1 — ticket_io | `pytest tests/test_ticket_io.py -v` | ✅ |
| Step 2 — tools | `pytest tests/test_tools.py -v` | ✅ 14/14 |
| Step 3 — dispatch | `pytest tests/test_runner_dispatch.py -v` | ✅ 11/11 |
| Step 4 — trajectory | `pytest tests/test_trajectory.py -v` | ✅ 13/13 |
| Step 5 — typed migration | `pytest tests/ -v` + zero grep hits | ✅ |
| Step 6 — skill cache | `pytest tests/ -v` 167 passed | ✅ |
| Step 7 — anchor+spawn | `pytest tests/ -v` 167 passed, 1 skipped | ✅ |
| Full suite | `pytest tests/ -v` | ✅ 167 passed, 1 skipped |

---

## For New AI Assistants

Start with `AI-FIRST/CONTEXT.md`. It tells you:
- What the system is
- What is currently validated
- What invariants must be true
- What you must not do
- Where to find the active spec

**Cold-start discipline:** Read `AI-FIRST/CONTEXT.md`, then the last line of
`logs/luffy-journal.jsonl` (anchor field). Do not read any other file until
you have a ticket with `context_files` in hand.

---

## Troubleshooting

See `TROUBLESHOOTING.md`. Common issues: journal corruption (split, don't rewrite),
import path errors (`sys.path.insert` required), YAML key mapping (`ticket_id` → `ticket.id`),
`&&` chaining on Windows (use `_shell_cmd()` in `tools/terminal.py`).
