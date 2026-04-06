---
project: HaloClaw
version: "0.1.0"
status: seed
created: 2026-04-05
author: MrSnowNB
hardware: ZBook (single node, first test)
default_max_depth: 2
---

# HaloClaw

> Hierarchical Autonomous Agent Swarm — recursive task decomposition over a local model mesh.

HaloClaw is a **self-optimizing swarm runtime** built on top of Lemonade Server (llama.cpp) and Meshtastic LoRa. The root agent (Operator) receives a problem, decomposes it into tickets, and routes sub-tasks to child agents at increasing depth. Swarm capability scales multiplicatively with node count and recursion depth.

**Origin:** The HaloClaw architecture was first observed emergently — an early agent session autonomously ran multi-hour model benchmarking, selected `Qwen3-Coder-Next-GGUF` (Qwen 7B variant) as the optimal tool-use model, and spun up a secondary Lemonade server instance to run it in parallel. That behavior is now the **first formal test protocol**.

---

## Architecture

```
Operator (Root, Depth 0)
├── Child Agent A (Depth 1)
│   ├── Child Agent A1 (Depth 2)  ← default leaf
│   └── Child Agent A2 (Depth 2)  ← default leaf
└── Child Agent B (Depth 1)
    └── Child Agent B1 (Depth 2)  ← default leaf
```

- **Max Depth:** variable, default `2`
- **Swarm power:** `N^D` where N = concurrent nodes, D = max depth
- **Message bus:** Meshtastic protobuf over 915MHz LoRa (single-node test: in-process queue)
- **Model backend:** Lemonade Server → llama.cpp GPU
- **Audit:** JSONL append-only log per session

---

## Repository Structure

```
haloclaw/
├── README.md                   ← this file
├── AGENT-POLICY.md             ← governance, lifecycle, validation gates
├── CLAUDE.md                   ← per-session agent task spec template
├── TROUBLESHOOTING.md          ← seeded failure catalog
├── REPLICATION-NOTES.md        ← living environment + run log
├── ISSUE.md                    ← open failure tickets
├── config/
│   └── settings.yaml           ← model slots, endpoints, depth config
├── protocols/
│   └── MODEL-SELECTION-TEST.md ← primary test protocol (model benchmarking)
├── tickets/
│   ├── open/                   ← active ticket YAML files
│   └── results/                ← completed ticket results
├── logs/                       ← JSONL audit logs per session
└── src/
    └── operator_v7.py          ← root agent (import from Liberty Mesh)
```

---

## Quick Start (Single Node, ZBook)

```bash
# 1. Confirm Lemonade is running
curl http://localhost:11434/api/v1/models

# 2. Check GPU VRAM headroom (need ~44GB for Qwen3-Coder-Next)
nvidia-smi

# 3. Run model selection test (Protocol MT-01)
python src/run_test.py --protocol MT-01 --max-depth 2

# 4. Tail audit log
tail -f logs/session_$(date +%Y%m%d).jsonl | python -m json.tool
```

---

## Core Concepts

| Term | Definition |
|---|---|
| **Operator** | Root agent at depth 0. Receives trigger, writes tickets, manages sessions. |
| **Ticket** | Atomic YAML job unit with `decrement`, `depth`, `model_slot`, `allowed_tools`. |
| **Decrement** | Countdown field. When it hits 0, ticket escalates and bubbles up. |
| **Depth** | Current nesting level. Leaf nodes run at `max_depth`. |
| **Swarm limit** | Max concurrent child agents. Power = `N^D`. |
| **Model slot** | Named model config in `settings.yaml`. Assigned per depth level. |
| **LCP similarity** | llama.cpp KV cache reuse score. High = fast TTFT. Target >0.7. |

---

## Validation Gates (all must pass before promotion)

| Gate | Command | Pass Criteria |
|---|---|---|
| Unit | `pytest -q` | Green, 0 failures |
| Lint | `ruff check src/` | Clean |
| Type | `mypy src/` | Clean |
| Spec drift | `python tools/spec_check.py` | No drift |
| Model test | Protocol MT-01 | 5/5 consecutive pass on selected model |

---

## Lifecycle

```
Plan → Build → Validate → Review → Release
```
Sequential only. No phase skipping. On any failure: update living docs → halt → wait for human input.
