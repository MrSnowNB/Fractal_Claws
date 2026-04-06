---
title: REPLICATION-NOTES.md
version: "0.1.0"
last_updated: "2026-04-05"
---

# REPLICATION-NOTES.md — Environment & Run Log

## Environment Setup

| Component | Value | Notes |
|-----------|-------|-------|
| Hardware | ZBook (single node) | Primary test machine |
| OS | Windows 11 | — |
| Python | TBD | Required for tools/ scripts |
| Lemonade | localhost:11434 | Ollama-compatible endpoint |
| Git | fc1783ef1213f0e65915253c7a2cdd21b14880cb | Latest commit |

---

## Model Inventory

| Model | Provider | Size | Status |
|-------|----------|------|--------|
| Qwen3-Coder-Next-GGUF | Lemonade | 43.7GB | Depth 0 (root) |
| Qwen3.5-35B-A3B-GGUF | Lemonade | 19.7GB | Depth 1 (worker) — TBD |
| lfm2.5-it-1.2b-FLM | Lemonade | NPU path | Depth 2 (leaf) |

---

## Performance Baselines

| Model | Prompt tok/s | Gen tok/s | TTFT (21k ctx) | TTFT (fresh) |
|-------|--------------|-----------|----------------|--------------|
| Qwen3-Coder-Next-GGUF | ~410 | ~35 | 12–22s | <1s |
| lfm2.5-it-1.2b-FLM | NPU | ~40 | <0.3s | <0.3s |
| Qwen3.5-35B-A3B-GGUF | TBD | TBD | TBD | TBD |

**Note:** KV cache anchor locks at ~16,372 tokens. Keep system prompt + ticket context under 16k for minimum TTFT.

---

## Recurring Errors

| Date | Issue | Resolution |
|------|-------|------------|
| — | — | — |

---

## Environment Deltas

| Date | Change | Impact |
|------|--------|--------|
| 2026-04-05 | Initial setup | Baseline established |

---

## MT-01 Run Log

### Run [2026-04-05] — Initial Baseline

| Model | Score | Pass? | Notes |
|-------|-------|-------|-------|
| lfm2.5-it-1.2b-FLM | — | — | Not yet tested |
| Qwen3.5-35B-A3B-GGUF | — | — | Not yet tested |
| Qwen3-Coder-Next-GGUF | — | — | Not yet tested |

---

## Run Instructions

1. Ensure Lemonade is running: `curl http://localhost:11434`
2. Run MT-01 protocol: `python src/run_test.py --protocol MT-01`
3. Check `logs/mt01_failures_YYYYMMDD.jsonl` for detailed logs
4. Update scoring matrix in MODEL-SELECTION-TEST.md

---

## Next Steps

- [ ] Run MT-01 on all models
- [ ] Update scoring matrix in MODEL-SELECTION-TEST.md
- [ ] If 28/30 achieved: unlock DT-01 (Depth Scaling Test)
| TS-20260405-TASK-005 | Ticket TASK-005 | Test failure... | 2026-04-05 22:13:44 |
| TS-20260405-TASK-005 | Ticket TASK-005 | Test failure... | 2026-04-05 22:14:28 |
