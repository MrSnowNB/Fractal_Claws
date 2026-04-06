---
title: Fractal Claws — 4B Child-Agent POC
version: "2.0"
---

# Fractal Claws

A proof-of-concept showing a 4B LLM acting as a **child agent** spawned by Cline, given only `read_file` and `write_file` tools, completing tasks via a standardized ticket queue.

---

## What This Is

- **Parent**: Cline (in VS Code) running `Qwen3.5-4B-GGUF` via Lemonade/Ollama
- **Child**: `agent/child_agent.py` — spawned by parent, receives one ticket YAML, reads context, writes result, exits
- **Ticket**: `tickets/template.yaml` — the contract between parent and child
- **Tools (child only)**: `tools/read_file.py`, `tools/write_file.py`

**One model. Two roles. No swarms. No browser. No cloud.**

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/MrSnowNB/Fractal_Claws.git
cd Fractal_Claws

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Ollama / Lemonade with Qwen3.5-4B-GGUF loaded
#    Endpoint must be live at http://localhost:11434/v1

# 4. Run pre-flight check
python pre_flight.py

# 5. Write a ticket (copy template)
cp tickets/template.yaml tickets/open/TASK-001.yaml
# edit TASK-001.yaml: fill ticket_id, task, context_files, result_path

# 6. Spawn the child
python agent/child_agent.py tickets/open/TASK-001.yaml

# 7. Check result
cat tickets/closed/TASK-001-result.md
```

---

## Repo Structure

```
Fractal_Claws/
├── .clinerules/            ← Cline rule files (parent config)
├── agent/
│   └── child_agent.py      ← the spawnable child
├── src/
│   ├── operator_v7.py      ← Liberty Mesh operator logic
│   └── tools/
│       └── first_principles_solver.py
├── tickets/
│   ├── template.yaml       ← ticket schema (copy this to create tickets)
│   ├── open/               ← parent writes here
│   ├── in_progress/        ← child moves ticket here on pickup
│   └── closed/             ← child writes result + closes ticket here
├── tools/
│   ├── read_file.py        ← child's read tool
│   └── write_file.py       ← child's write tool
├── tests/
├── CLAUDE.md               ← Cline reads this first
├── AGENT-POLICY.md
├── TROUBLESHOOTING.md
├── REPLICATION-NOTES.md
├── settings.yaml
├── pre_flight.py
└── requirements.txt
```

---

## Ticket Flow

```
parent writes → tickets/open/<id>.yaml
parent spawns → python agent/child_agent.py tickets/open/<id>.yaml
child moves   → tickets/in_progress/<id>.yaml
child writes  → result_path (defined in ticket)
child closes  → tickets/closed/<id>.yaml
parent polls  → reads result_path, continues
```

---

## POC Success Criteria

- [ ] Child picks up ticket, reads context file, writes result
- [ ] `pytest -q tests/` passes (0 failures)
- [ ] `ruff check src/` clean
- [ ] Child exits 0 on success, 1 on failure
- [ ] Ticket audit log populated in `attempts` field

---

## Config

See `settings.yaml`. Single model slot: `Qwen3.5-4B-GGUF` at `http://localhost:11434/v1`.

---

## Troubleshooting

See `TROUBLESHOOTING.md`. Key known issue: `H-API-001` — browser tool calls fail on 4B model. Use `tools/read_file.py` instead.
