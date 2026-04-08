---
title: Fractal Claws — Self-Healing Recursive Agent Harness
version: "4.0"
gate: "step-3-validated — 2026-04-07"
---

# Fractal Claws

A local agentic harness where a **parent agent** (Cline in VS Code) decomposes
a goal into tickets, and a **child runner** (`agent/runner.py`) picks them up,
executes tool calls, writes results, and closes them. Tickets are YAML files.
The contract between parent and child is the `Ticket` dataclass in `src/operator_v7.py`.

**One harness. Two roles. No swarms. No browser. No cloud.**

> **Current gate (2026-04-07):** Steps 1–3 complete and validated.
> `pytest tests/` → all green. Registry wired. Journal-first commit protocol active.
> Step 4 (Trajectory Extractor) is next.

---

## What This Is

| Component | What it does |
|---|---|
| **Parent** | Cline (VS Code) — orchestrates via `.clinerules/`, writes tickets to `tickets/open/` |
| **Runner** | `agent/runner.py` — decompose goal → drain queue → execute → close tickets |
| **Ticket** | `src/operator_v7.py:Ticket` — canonical dataclass; `tickets/template.yaml` is the on-disk schema |
| **Registry** | `tools/registry.py` — dynamic tool dispatch; replaces hardcoded if/elif in runner |
| **Terminal** | `tools/terminal.py` — subprocess wrapper with DANGEROUS_PATTERNS denylist and timeout |
| **Tools** | `read_file`, `write_file`, `exec_python`, `list_dir`, `run_command` — sandboxed |
| **Audit log** | `logs/<id>-attempts.jsonl` — append-only, one JSON record per attempt |
| **Journal** | `logs/luffy-journal.jsonl` — Luffy Law: written before every git commit |

The model endpoint is configured in `settings.yaml`. Any OpenAI-compatible local endpoint
(Lemonade, Ollama, LM Studio) works — no model names are hardcoded in the runner.

---

## Build Progress

| Step | What | Status |
|---|---|---|
| Step 1 | Typed Ticket I/O Bridge (`src/ticket_io.py`) | ✅ DONE |
| Step 2 | Terminal Tool + Tool Registry (`tools/terminal.py`, `tools/registry.py`) | ✅ DONE |
| Step 3 | Wire Registry into runner.py (dynamic dispatch, 11 tests) | ✅ DONE |
| Step 4 | Trajectory Extractor (`src/trajectory_extractor.py`) | 🔨 In Progress |
| Step 5 | Full Phase A Migration of runner.py (typed field access) | ⏳ Queued |

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

Before every `git commit`, Luffy (the coding agent) must:

1. `pytest tests/` — gate must be green
2. Append a JSONL entry to `logs/luffy-journal.jsonl`
3. `git add <changed files> logs/luffy-journal.jsonl`
4. `git commit -m "STEP-XX: description"`
5. `git push`

Journal entry schema:
```json
{"ts": "ISO-8601", "step": "STEP-XX-Y", "action": "...", "status": "done", "files": [...]}
```

---

## Repo Structure

```
Fractal_Claws/
├── AI-FIRST/                    ← Start here if you are a new AI assistant
│   ├── CONTEXT.md               ← System overview + current state
│   ├── ARCHITECTURE.md          ← Dataclass map, ticket lifecycle, module inventory
│   ├── NEXT-STEPS.md            ← Build queue and open work
│   ├── STEP-01-TICKET-IO.md
│   ├── STEP-02-TERMINAL-REGISTRY.md
│   ├── STEP-03-RUNNER-WIRING.md
│   └── STEP-04-TRAJECTORY.md    ← Active spec
├── .clinerules/                 ← Cline rule files (parent config)
├── agent/
│   └── runner.py                ← Decompose + drain loop (registry-wired)
├── src/
│   ├── operator_v7.py           ← Ticket, TicketStatus, TicketPriority, TicketDepth
│   ├── ticket_io.py             ← Typed ticket loading + as_dict() shim
│   └── trajectory_extractor.py  ← Step 4 target
├── tickets/
│   ├── template.yaml
│   ├── open/
│   ├── in_progress/
│   ├── closed/
│   └── failed/
├── tools/
│   ├── registry.py              ← Dynamic tool registry (Step 2)
│   ├── terminal.py              ← subprocess wrapper + denylist (Step 2)
│   ├── read_file.py
│   └── write_file.py
├── tests/
│   ├── conftest.py
│   ├── test_multistep_harness.py
│   ├── test_ticket_io.py
│   ├── test_tools.py            ← 14 tests (Step 2)
│   ├── test_runner_dispatch.py  ← 11 tests (Step 3)
│   └── test_trajectory.py       ← Step 4 target
├── logs/
│   ├── luffy-journal.jsonl      ← Luffy Law audit trail
│   └── <id>-attempts.jsonl      ← Per-ticket attempt logs
├── output/                      ← exec_python sandbox
├── skills/                      ← Step 4 output: compressed toolpaths
├── CLAUDE.md
├── AGENT-POLICY.md
├── settings.yaml
├── pre_flight.py
└── requirements.txt
```

---

## Ticket Lifecycle

```
parent writes   → tickets/open/<id>.yaml
runner picks up → tickets/in_progress/<id>.yaml
runner executes → tool calls via REGISTRY.call(), writes result to logs/<id>-result.txt
runner closes   → tickets/closed/<id>.yaml   (on pass)
                → tickets/failed/<id>.yaml   (on max depth / deadlock)
audit appended  → logs/<id>-attempts.jsonl   (one line per attempt)
journal updated → logs/luffy-journal.jsonl   (before every commit)
parent reads    → result file, continues or escalates
```

---

## Audit Log Format (JSONL)

```json
{"ts": "2026-04-07T07:30:00", "attempt": 1, "outcome": "pass",
 "tokens": 412, "elapsed_s": 3.2, "finish": "stop"}
```

Append-only. Never rewrite. `tail -f logs/*.jsonl` for live monitoring.

---

## Validation Gates

| Gate | Tests | Status |
|---|---|---|
| Step 1 — ticket_io | `pytest tests/test_ticket_io.py -v` | ✅ |
| Step 2 — tools | `pytest tests/test_tools.py -v` | ✅ 14/14 |
| Step 3 — dispatch | `pytest tests/test_runner_dispatch.py -v` | ✅ 11/11 |
| Step 4 — trajectory | `pytest tests/test_trajectory.py -v` | 🔨 in progress |
| Full suite | `pytest tests/ -v` | ✅ all green |

---

## Config

See `settings.yaml`. Key fields:
- `model.id` — model identifier string sent to the endpoint
- `model.endpoint` — OpenAI-compatible base URL
- `model.depth_map` — maps ticket depth (0/1/2) to model slot

See `AI-FIRST/ARCHITECTURE.md` for the full depth/model mapping.

---

## Troubleshooting

See `TROUBLESHOOTING.md`. For new AI assistants onboarding to this codebase,
start with `AI-FIRST/CONTEXT.md`.
