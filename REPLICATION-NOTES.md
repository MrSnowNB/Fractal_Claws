---
title: REPLICATION-NOTES.md
version: "2.0"
last_updated: "2026-04-06"
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
| Git branch | poc/child-agent |

**NOT a Z8. Do not use Z8 ports, specs, or model sizes.**

## Model

| Field | Value |
|-------|-------|
| Model ID | Qwen3.5-4B-GGUF |
| RAM used | ~27 GB |
| Gen tok/s | ~40.9 |
| TTFT | ~0.96s |
| Context window | 8,192 tokens |

All other model slots (35B, Hermes, LFM2.5, Qwen3-Coder-Next) are NOT active.

## Session Startup

```powershell
curl http://localhost:8000/api/v1/models
python pre_flight.py
```

## Known Issues

| ID | Date | Description | Status |
|----|------|-------------|--------|
| H-API-001 | 2026-04-05 | Browser tool calls fail on 4B | Forbidden in policy |
| H-API-005 | 2026-04-06 | Model unloads on idle timeout | Keep Lemonade active |
| H-SCOPE-001 | 2026-04-06 | Agent self-installed fastmcp | Forbidden in .clinerules |
| H-CONFLICT-001 | 2026-04-06 | Merge conflict in pre_flight.py | Fixed |

## Environment Deltas

| Date | Change |
|------|--------|
| 2026-04-05 | Initial setup |
| 2026-04-06 | Rescoped to 4B single-model POC |
| 2026-04-06 | Removed fastmcp 3.1.0 |
| 2026-04-06 | Fixed pre_flight.py merge conflict |
| 2026-04-06 | All configs locked to ZBook / Lemonade :8000 |

## POC Success Criteria

- [ ] python pre_flight.py exits 0
- [ ] child_agent.py completes ticket end-to-end
- [ ] Child reads context, writes result, closes ticket
- [ ] pytest -q tests/ passes
- [ ] ruff check src/ clean
