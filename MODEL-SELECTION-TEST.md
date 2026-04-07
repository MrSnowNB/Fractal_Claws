---
title: "Model Selection Test Results"
version: "2026-04-07"
last_updated: "2026-04-07"
---

# Model Selection Test Results

## Decision: Stick with A3B (lfm2.5-it-1.2b-FLM)

### 4B Model Test Results

| Model | ID | Status | Issue |
|-------|-----|--------|-------|
| Qwen3.5-4B-GGUF | Qwen3.5-4B-GGUF | **Unavailable** | Empty choices on decompose task |

### Test Command
```bash
python agent/runner.py --goal "write a python script that generates the first 20 fibonacci numbers and saves them to output/fib.txt, then verify the file was written"
```

### Observed Behavior (4B Model)
- Model call returns `empty choices` consistently
- 4 retry attempts exhausted before failure
- Decompose phase fails after multiple timeouts
- Task cannot be decomposed into tickets

### Root Cause Analysis
- 4B model cannot handle decompose prompt within timeout
- Empty `response.choices` returned after timeout
- Token budget insufficient for YAML generation

### Final Configuration

```yaml
model:
  id: lfm2.5-it-1.2b-FLM  # A3B model - working
  endpoint: http://localhost:8000/api/v1
  timeout_seconds: 180
  max_retries: 3
  decompose_budget: 2048
```

### Files Updated
- `settings.yaml` - Model ID set to A3B
- `TROUBLESHOOTING.md` - 4B failure documented
- `ISSUE.md` - 4B unavailable issue created
- `REPLICATION-NOTES.md` - Environment deltas logged

### Recommendation
Use A3B (lfm2.5-it-1.2b-FLM) for all tasks until 4B model issues are resolved.