---
title: Fractal Claws — Self-Healing Recursive Agent Harness
version: "3.0"
gate: "ticketing-validated — 2026-04-07"
---

# Fractal Claws

A proof-of-concept agentic harness where a **parent agent** (Cline in VS Code) decomposes
a goal into tickets, and a **child runner** (`agent/runner.py`) picks them up, executes
tool calls, writes results, and closes them. Tickets are YAML files. The contract between
parent and child is the `Ticket` dataclass defined in `src/operator_v7.py`.

**One harness. Two roles. No swarms. No browser. No cloud.**

> **Current gate (2026-04-07):** Ticketing system validated. `pytest tests/` → 6/6 passed.
> All phases of the multistep harness green. Safe to build Phase 3 (OpenClaw tool registry)
> on top of this foundation.

---

## What This Is

| Component | What it does |
|---|---|
| **Parent** | Cline (VS Code) — orchestrates via `.clinerules/`, writes tickets to `tickets/open/` |
| **Runner** | `agent/runner.py` — decompose goal → drain queue → execute → close tickets |
| **Ticket** | `src/operator_v7.py:Ticket` — canonical dataclass; `tickets/template.yaml` is the on-disk schema |
| **Tools** | `read_file`, `write_file`, `exec_python`, `list_dir` — child-only, sandboxed to `output/` |
| **Audit log** | `logs/<id>-attempts.jsonl` — append-only, one JSON record per attempt |

The model endpoint is configured in `settings.yaml`. Any OpenAI-compatible local endpoint
(Lemonade, Ollama, LM Studio) works — no model names are hardcoded in the runner.

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

## Repo Structure

```
Fractal_Claws/
├── AI-FIRST/                    ← Start here if you are a new AI assistant
│   ├── CONTEXT.md               ← What this system is + current state
│   ├── ARCHITECTURE.md          ← Dataclass map, ticket lifecycle, module inventory
│   └── NEXT-STEPS.md            ← Phase 3 roadmap and open work
├── .clinerules/                 ← Cline rule files (parent config)
├── agent/
│   └── runner.py                ← Active harness: decompose + drain
├── src/
│   ├── operator_v7.py           ← Ticket, TicketStatus, TicketPriority, TicketDepth
│   └── tools/
│       └── first_principles_solver.py
├── tickets/
│   ├── template.yaml            ← Ticket schema (copy to create tickets)
│   ├── open/                    ← Parent writes here (gitignored at runtime)
│   ├── in_progress/             ← Runner moves ticket here on pickup
│   ├── closed/                  ← Runner closes ticket here on pass
│   └── failed/                  ← Runner moves ticket here on max depth
├── tools/
│   ├── read_file.py
│   └── write_file.py
├── tests/
│   ├── conftest.py              ← Fixture: Ticket(test_mode=True)
│   ├── test_multistep_harness.py ← PRIMARY GATE — 6/6 validated 2026-04-07
│   ├── test_operator.py
│   ├── test_harness_artifacts.py
│   ├── test_first_principles_solver.py
│   └── test_solver_init.py
├── logs/                        ← JSONL audit logs + result files
├── output/                      ← exec_python sandbox
├── experiments/                 ← Daemon and LLM loop experiments
├── CLAUDE.md                    ← Cline reads this first
├── AGENT-POLICY.md
├── TROUBLESHOOTING.md
├── REPLICATION-NOTES.md
├── VISION.md
├── OPENCLAW-PLAN.md
├── settings.yaml
├── pre_flight.py
└── requirements.txt
```

---

## Ticket Lifecycle

```
parent writes   → tickets/open/<id>.yaml
runner picks up → tickets/in_progress/<id>.yaml
runner executes → tool calls, writes result to logs/<id>-result.txt
runner closes   → tickets/closed/<id>.yaml   (on pass)
                → tickets/failed/<id>.yaml   (on max depth / deadlock)
audit appended  → logs/<id>-attempts.jsonl   (one line per attempt)
parent reads    → result file, continues or escalates
```

**Dependency graph:** tickets declare `depends_on: [TASK-XYZ]`. The runner
defers a ticket if any dependency has not yet reached `closed/`. A ticket
blocked with no runnable peers is a deadlock — runner prints the dependency
graph and exits 1.

---

## Audit Log Format (JSONL)

```json
{"ts": "2026-04-07T07:30:00", "attempt": 1, "outcome": "pass",
 "tokens": 412, "elapsed_s": 3.2, "finish": "stop"}
```

Append-only. Never rewrite. `tail -f logs/*.jsonl` for live monitoring.

---

## Validation Gate (2026-04-07)

| Check | Status |
|---|---|
| `pytest tests/test_multistep_harness.py -v` | ✅ 6/6 passed |
| `pytest tests/test_operator.py -v` | ✅ passing |
| `python agent/runner.py --no-prewarm` (TASK-003 dep on TASK-002) | ✅ deadlock correctly detected |
| Ticket dataclass `from_dict` / `to_dict` round-trip | ✅ validated |
| Parent/child wiring via `Ticket.from_dict` | ✅ validated |

---

## Config

See `settings.yaml`. Key fields:
- `model.id` — model identifier string sent to the endpoint
- `model.endpoint` — OpenAI-compatible base URL
- `model.depth_map` — maps ticket depth (0/1/2) to model slot

See `AI-FIRST/ARCHITECTURE.md` for the full depth/model mapping.

---

## Troubleshooting

See `TROUBLESHOOTING.md`. For new AI assistants onboarding to this codebase, start
with `AI-FIRST/CONTEXT.md`.
