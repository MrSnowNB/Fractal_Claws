---
title: ISSUE.md — Open Issue Tracker
version: "0.1.0"
last_updated: "2026-04-05"
---

# ISSUE.md — Open Issues

## New Issues

| ID | Title | Status | Blocked On | Created |
|----|-------|--------|------------|---------|
| ISS-001 | Run MT-01 baseline test on all models | open | agent | 2026-04-05 |
| ISS-002 | Validate settings.yaml Lemonade endpoint | open | agent | 2026-04-05 |
| ISS-003 | Create src/operator_v7.py skeleton | open | agent | 2026-04-05 |

---

## Issue Template

```yaml
ISS-XXX:
  title: <one-line summary>
  status: open | closed
  blocked_on: agent | human | system | other
  created: "YYYY-MM-DD"
  updated: "YYYY-MM-DD"
  priority: low | medium | high | critical
  description: |
    <multi-line description>
  steps_to_reproduce:
    - Step 1
    - Step 2
    - Step 3
  expected_behavior: <description>
  actual_behavior: <description>
  logs:
    - logs/ISS-XXX-YYYYMMDD.log
  resolution: |
    <if closed>
  assignee: <if assigned>
```

---

## Resolution Procedure

1. **Assignee** investigates and implements fix
2. **Assignee** updates resolution field with details
3. **Assignee** runs MT-01 protocol to verify fix
4. **Assignee** updates status: closed
5. Human reviews and confirms closure