---
title: REPLICATION-NOTES.md
version: "4.0"
last_updated: "2026-04-07"
---

# REPLICATION-NOTES.md

## Hardware

| Component | Value |
|-----------|-------|
| Machine | HP ZBook (single node) |
| OS | Windows 11 |
| Python | 3.10 (64-bit) |
| Lemonade endpoint | http://localhost:8000/api/v1 |
| API key | x |
| Git branch | main |

**NOT a Z8. Do not use Z8 ports, specs, or model sizes.**

---

## Active Models (as of 2026-04-07)

| Model ID | Size | ctx_size | Status | Role |
|----------|------|----------|--------|------|
| Qwen3-Coder-Next-GGUF | 43.7 GB | 64,000 | ✅ Loaded | **Parent** — Cline orchestrator |
| Qwen3.5-35B-A3B-GGUF | 19.7 GB | 64,000 | ✅ Loaded | **Child** — runner.py executor |
| Qwen3.5-4B-GGUF | 2.91 GB | TBD | ⛔ DEPRECATED | Future leaf/worker — do not use in active sessions |
| lfm2.5-it-1.2b-FLM | 0.96 GB | — | Loaded | Tiny health checks only |
| Whisper-Base | 0.14 GB | — | Loaded | Audio/transcription |
| kokoro-v1 | 0.34 GB | — | Loaded | TTS |
| user.Hermes-3-Llama-3.1-8B-GGUF | — | — | Downloaded | Reserved |

---

## Session Startup

```powershell
# 1. Verify Lemonade is running and A3B is loaded
python -c "import requests; r = requests.post('http://localhost:8000/api/v1/chat/completions', json={'model': 'Qwen3.5-35B-A3B-GGUF', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 10}); print(r.status_code, r.text[:100])"

# 2. Run pre-flight (probes A3B by default)
python pre_flight.py

# 3. Run agent
python agent/runner.py --goal "<your goal here>"
```

---

## Known Issues

| ID | Date | Description | Status |
|----|------|-------------|--------|
| H-API-001 | 2026-04-05 | Browser tool calls fail | Forbidden in policy |
| H-API-005 | 2026-04-06 | Model unloads on idle timeout | Keep Lemonade active |
| H-SCOPE-001 | 2026-04-06 | Agent self-installed fastmcp | Forbidden in .clinerules |
| H-CONFLICT-001 | 2026-04-06 | Merge conflict in pre_flight.py | Fixed |
| ISS-20260406-001 | 2026-04-06 | Empty choices / 4B not loaded | RESOLVED 2026-04-07 |
| ISS-20260407-001 | 2026-04-07 | Qwen3.5-4B-GGUF cannot produce valid YAML | DEPRECATED — deferred, not a blocker |

---

## Environment Deltas

| Date | Change |
|------|--------|
| 2026-04-05 | Initial setup |
| 2026-04-06 | Rescoped to single-model POC |
| 2026-04-06 | Removed fastmcp 3.1.0 |
| 2026-04-06 | Fixed pre_flight.py merge conflict |
| 2026-04-06 | All configs locked to ZBook / Lemonade :8000 |
| 2026-04-07 | **MILESTONE**: First full end-to-end POC run — fib.txt, 8 tickets PASS (A3B model) |
| 2026-04-07 | **REFACTOR**: 4B formally deprecated; harness locked to Coder-Next (parent) + A3B (child) |
| 2026-04-07 | settings.yaml context_window updated to 64000 (A3B actual); 4B perf block removed |
| 2026-04-07 | pre_flight.py default probe target switched to A3B; 4B alias hard-blocked with warning |

---

## POC Success Criteria

- [x] python pre_flight.py exits 0
- [x] runner.py completes ticket end-to-end
- [x] Agent reads context, writes result, closes ticket
- [ ] pytest -q tests/ passes
- [ ] ruff check src/ clean

---

## Performance Baseline (2026-04-07, Qwen3.5-35B-A3B-GGUF as child)

| Metric | Value |
|--------|-------|
| Decompose tokens | 609 |
| Decompose time | 10.43s |
| Peak tok/s | 126.8 (TASK-014) |
| Min tok/s | 54.7 (TASK-015) |
| RAM used | ~98.6 GB / 127 GB |
| All tickets | 8/8 PASS |
