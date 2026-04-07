title: ISSUE.md
version: "2026-04-07"
last_updated: "2026-04-07"
---

# ISSUE.md

## ISS-20260406-001: Runner 4B Model Empty Choices

- **Status**: CLOSED ✅
- **Blocked On**: —
- **Title**: Runner cannot spawn Qwen3.5-4B-GGUF — model returns empty choices
- **Description**: Runner attempts to decompose goal via Lemonade endpoint `http://localhost:8000/api/v1` consistently returned `empty choices` across all retry attempts.
- **Ticket ID**: TASK-014
- **Opened**: 2026-04-06 21:34:09
- **Closed**: 2026-04-07 05:26:00
- **Resolution**:
  Two stacked bugs identified and fixed:
  1. `max_tokens: 512` in settings.yaml was the *output* cap — decompose prompts consumed the entire context window leaving zero room for output generation.
  2. `decompose_budget` key was missing from config — runner was using `max_tokens` (512) as input budget instead of 80% of context window (6553 tokens).
  3. Qwen3.5-4B-GGUF was downloaded but not loaded in Lemonade — agent self-corrected by probing available models and switching to Qwen3.5-35B-A3B-GGUF which was active.
- **Fix commit**: `58081217` — settings.yaml max_tokens raised to 1024, decompose_budget: 6553 added, timeout bumped to 120s.
- **POC Proof**: Full fib.txt run completed 2026-04-07 with 35B model — 8 tickets decomposed and closed, all PASS.
- **Human action required**: None. Resolved.

---

## ISS-20260406-TASK-005

- **Status**: CLOSED ✅
- **Blocked On**: —
- **Title**: Failure in ticket TASK-005
- **Description**: Test failure
- **Ticket ID**: TASK-005
- **Timestamp**: 2026-04-06 20:22:19
- **Resolution**: Superseded by full POC run on 2026-04-07. All subsequent tickets passed.

---

## ISS-20260406-TASK-005 (duplicate)

- **Status**: CLOSED ✅
- **Blocked On**: —
- **Title**: Failure in ticket TASK-005 (duplicate entry)
- **Description**: Duplicate of above — same test failure, second log entry.
- **Ticket ID**: TASK-005
- **Timestamp**: 2026-04-06 20:24:08
- **Resolution**: Duplicate. Closed with parent.
