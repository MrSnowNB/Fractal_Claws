---
title: Fractal Claws — Self-Healing Recursive Agent Harness
version: "5.0"
gate: "step-4-validated — 2026-04-07"
---

# Fractal Claws

A local agentic harness where a **parent agent** (Cline in VS Code) decomposes
a goal into tickets, and a **child runner** (`agent/runner.py`) picks them up,
executes tool calls, writes results, and closes them.

Tickets are YAML files. The contract between parent and child is the `Ticket`
dataclass in `src/operator_v7.py`. The system improves over time: after every
passing run, a trajectory extractor writes `skills/<goal-class>.yaml` so the
next matching goal skips decomposition entirely.

**One harness. Two roles. Executable memory. No cloud.**

> **Current gate (2026-04-07):** Steps 1–4 complete and validated.
> `pytest tests/ -v` → 38+ tests, all green.
> Step 5 (Full Typed Field Migration of runner.py) is active.

---

## How It Works

```
Human gives goal
  → Cline reads skills/ — skips decomposition if goal class known
  → Cline decomposes → writes tickets/open/*.yaml
  → runner picks up tickets in dependency order
  → runner calls REGISTRY.call(tool, args) — dynamic dispatch
  → runner writes result to logs/<id>-result.txt
  → runner closes ticket → tickets/closed/<id>.yaml
  → trajectory extractor reads closed tickets → writes skills/
  → Cline reads result, continues or escalates
```

---

## Components

| Component | What it does |
|---|---|
| **Parent** | Cline (VS Code) — orchestrates via `.clinerules/`, writes tickets |
| **Runner** | `agent/runner.py` — decompose → drain → execute → close |
| **Ticket** | `src/operator_v7.py:Ticket` — typed dataclass; `tickets/template.yaml` is on-disk schema |
| **Registry** | `tools/registry.py` — dynamic dispatch; no hardcoded if/elif |
| **Terminal** | `tools/terminal.py` — subprocess wrapper with DANGEROUS_PATTERNS denylist |
| **Ticket I/O** | `src/ticket_io.py` — typed YAML loader + as_dict() shim |
| **Trajectory** | `src/trajectory_extractor.py` — reads closed tickets, writes skills/ |
| **Skills** | `skills/<goal-class>.yaml` — executable memory: winning toolpaths by goal class |
| **Audit log** | `logs/<id>-attempts.jsonl` — append-only, one JSON record per attempt |
| **Journal** | `logs/luffy-journal.jsonl` — Luffy Law: written before every git commit |

---

## Build Progress

| Step | What | Gate | Status |
|---|---|---|---|
| 1 | Typed Ticket I/O Bridge (`src/ticket_io.py`) | `pytest tests/test_ticket_io.py` | ✅ DONE |
| 2 | Terminal Tool + Tool Registry | `pytest tests/test_tools.py` 14/14 | ✅ DONE |
| 3 | Wire Registry into runner.py | `pytest tests/test_runner_dispatch.py` 11/11 | ✅ DONE |
| 4 | Trajectory Extractor + skills/ | `pytest tests/test_trajectory.py` 13/13 | ✅ DONE |
| 5 | Full Typed Field Migration of runner.py | `pytest tests/ -v` + zero grep hits | 🔥 ACTIVE |
| 6 | Skill-Aware Decomposition + OpenClaw spawning | TBD | ⏳ Queued |

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
```

---

## Luffy Law — Commit Protocol

Before every `git commit`, the coding agent must:

1. `pytest tests/` — all green
2. Append a JSONL entry to `logs/luffy-journal.jsonl`
3. `git add <changed files> logs/luffy-journal.jsonl`
4. `git commit -m "STEP-XX: description"`
5. `git push`

**Journal integrity is a hard invariant.** Every line must be valid JSON + `\n`.
A malformed line is fixed by splitting (never rewriting) before the next entry is written.

Journal entry schema:
```json
{"ts": "ISO-8601", "step": "STEP-XX-Y", "action": "...", "status": "done", "files": [...]}
```

---

## First Principles

Fractal Claws agents reason from invariants, not just instructions:

1. **What invariant must be true?** (green tests, valid journal, typed contract, dep order)
2. **What is the actual current state?** (read the filesystem, verify don’t assume)
3. **What is the minimal intervention?** (fix the line, add the field, don’t rebuild)

The `AI-FIRST/` folder is the system’s self-description. An agent that reads it
can audit state, find violations, and self-correct — without asking.

---

## Repo Structure

```
Fractal_Claws/
├── AI-FIRST/                    ← Start here if you are a new AI assistant
│   ├── CONTEXT.md               ← System overview + current state (read first)
│   ├── AGENT-PERSONA.md         ← Luffy: first principles, HALT, Luffy Law
│   ├── ARCHITECTURE.md          ← Dataclass map, ticket lifecycle, module inventory
│   ├── NEXT-STEPS.md            ← Build queue and open work
│   ├── STEP-01-TICKET-IO.md
│   ├── STEP-02-TERMINAL-REGISTRY.md
│   ├── STEP-03-RUNNER-WIRING.md
│   ├── STEP-04-TRAJECTORY.md
│   └── STEP-05-RUNNER-MIGRATION.md  ← Active spec
├── .clinerules/                 ← Cline rule files (parent config)
├── agent/
│   └── runner.py                ← Decompose + drain loop (Step 5: dict → typed)
├── src/
│   ├── operator_v7.py           ← Ticket, TicketStatus, TicketPriority, TicketDepth
│   ├── ticket_io.py             ← Typed ticket loading + as_dict() shim
│   └── trajectory_extractor.py  ← Post-run pass → writes skills/ (Step 4 ✅)
├── tickets/
│   ├── template.yaml
│   ├── open/
│   ├── in_progress/
│   ├── closed/
│   └── failed/
├── tools/
│   ├── registry.py              ← Dynamic tool registry (Step 2 ✅)
│   ├── terminal.py              ← subprocess wrapper + denylist (Step 2 ✅)
│   ├── read_file.py
│   └── write_file.py
├── tests/
│   ├── conftest.py
│   ├── test_multistep_harness.py
│   ├── test_ticket_io.py
│   ├── test_tools.py
│   ├── test_runner_dispatch.py
│   └── test_trajectory.py
├── logs/
│   ├── luffy-journal.jsonl      ← Luffy Law audit trail
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
| Step 5 — typed migration | `pytest tests/ -v` + `grep -n 'ticket\.get\|ticket\[' agent/runner.py` | 🔥 ACTIVE |
| Full suite | `pytest tests/ -v` | ✅ 38+ green |

---

## For New AI Assistants

Start with `AI-FIRST/CONTEXT.md`. It tells you:
- What the system is
- What is currently validated
- What invariants must be true
- What you must not do
- Where to find the active spec

Do not act before reading it. The folder is the memory. You are the reader.

---

## Troubleshooting

See `TROUBLESHOOTING.md`. Common issues: journal corruption (split, don’t rewrite),
import path errors (`sys.path.insert` required), YAML key mapping (`ticket_id` → `ticket.id`).
