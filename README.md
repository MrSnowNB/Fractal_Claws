---
title: Fractal Claws — Single-Parent / Single-Child POC
version: "2.1"
---

# Fractal Claws

A proof-of-concept showing a **parent agent** (Cline harness) spawning a **single child agent** to solve a multi-step problem using a standardized ticket queue. The child receives one ticket YAML, reads context, executes tool calls, writes a result, and exits. The parent evaluates the result and iterates.

**One harness. Two roles. No swarms. No browser. No cloud.**

---

## What This Is

- **Parent**: Cline (in VS Code) acting as orchestrator via the custom harness
- **Child**: `agent/runner.py` — receives a ticket YAML, works through the problem sequentially, writes result, exits
- **Ticket**: `tickets/template.yaml` — the contract between parent and child
- **Audit log**: JSONL — one record per attempt, appended; never rewritten
- **Tools (child only)**: `read_file`, `write_file`, `exec_python`, `list_dir`

The model endpoint is configured in `settings.yaml`. This repo is model-agnostic — any OpenAI-compatible local endpoint works.

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/MrSnowNB/Fractal_Claws.git
cd Fractal_Claws

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your endpoint
#    Edit settings.yaml — set model.id and model.endpoint

# 4. Run pre-flight check
python pre_flight.py

# 5. Decompose a goal and drain the ticket queue
python agent/runner.py --goal "<your goal here>"

# 6. Or drop a ticket manually and run once
cp tickets/template.yaml tickets/open/TASK-001.yaml
# edit TASK-001.yaml: fill ticket_id, task, context_files, result_path
python agent/runner.py --once

# 7. Check result
cat logs/TASK-001-result.txt
```

---

## Repo Structure

```
Fractal_Claws/
├── .clinerules/            ← Cline rule files (parent config)
├── agent/
│   └── runner.py           ← active harness: decompose + drain
├── src/
│   └── tools/
│       └── first_principles_solver.py
├── tickets/
│   ├── template.yaml       ← ticket schema (copy to create tickets)
│   ├── open/               ← parent writes here
│   ├── in_progress/        ← runner moves ticket here on pickup
│   ├── closed/             ← runner closes ticket here on pass
│   └── failed/             ← runner moves ticket here on max depth
├── tools/
│   ├── read_file.py
│   └── write_file.py
├── logs/                   ← JSONL audit logs + result files
├── output/                 ← exec_python sandbox
├── tests/
├── CLAUDE.md               ← Cline reads this first
├── AGENT-POLICY.md
├── TROUBLESHOOTING.md
├── REPLICATION-NOTES.md
├── VISION.md
├── settings.yaml
├── pre_flight.py
└── requirements.txt
```

---

## Ticket Flow

```
parent writes  → tickets/open/<id>.yaml
runner picks up → tickets/in_progress/<id>.yaml
runner executes → tool calls, writes result to logs/<id>-result.txt
runner closes  → tickets/closed/<id>.yaml   (on pass)
               → tickets/failed/<id>.yaml   (on max depth)
audit appended → logs/<id>-attempts.jsonl   (one line per attempt)
parent reads   → result file, continues or escalates
```

---

## Audit Log Format (JSONL)

Each attempt appends one JSON object to `logs/<ticket_id>-attempts.jsonl`:

```json
{"ts": "2026-04-07T07:30:00", "attempt": 1, "outcome": "pass", "tokens": 412, "elapsed_s": 3.2, "finish": "stop"}
```

Append-only. Never rewrite. `tail -f logs/*.jsonl` for live monitoring.

---

## POC Success Criteria

- [ ] Child picks up ticket, reads context file, writes result
- [ ] `pytest -q tests/` passes (0 failures)
- [ ] `ruff check src/` clean
- [ ] Runner exits 0 on success, 1 on failure
- [ ] JSONL audit log populated per ticket

---

## Config

See `settings.yaml`. Set `model.id` and `model.endpoint` for your local inference server. No model names are hardcoded in the runner — the endpoint must be OpenAI-compatible.

---

## Troubleshooting

See `TROUBLESHOOTING.md`.
