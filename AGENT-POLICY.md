---
title: AGENT-POLICY.md — Operator Policy
version: "0.1.0"
last_updated: "2026-04-05"
---

# AGENT-POLICY.md — Self-Healing Recursive First Principles Operator

## Core Mandates

1. **Atomicity** — One clear, bounded objective per task.
2. **Testability** — Binary pass/fail outcome must be definable before work begins.
3. **Gating** — No phase transition without green gate.
4. **Failure Handling** — On any failure or uncertainty, trigger the 5-step failure procedure.

---

## Lifecycle (Sequential Only)

```
Plan → Build → Validate → Review → Release
```

| Phase | Entry Condition | Exit Gate |
|-------|-----------------|-----------|
| Plan | Human approves task scope | Spec written, reviewed by human |
| Build | Spec approved | All validation gates green |
| Validate | Build complete | All four validation suites pass |
| Review | Validation green | Human approves diff |
| Release | Human approval | Artifact tagged and documented |

---

## Validation Gates

All four gates must be green before Build→Validate→Review transition:

```yaml
gates:
  unit:
    command: "pytest -q"
    pass_condition: "0 failed, 0 errors"
  lint:
    command: "ruff check . || flake8 ."
    pass_condition: "clean output"
  type:
    command: "mypy . || pyright ."
    pass_condition: "0 errors"
  docs:
    command: "spec drift check"
    pass_condition: "no unresolved drift"
```

---

## Failure Handling Procedure

When any step fails or the agent is uncertain:

1. **capture_logs()** — Save full stdout/stderr to `logs/ISS-<date>-<short-description>.log`
2. **update_troubleshooting()** — Append entry to `TROUBLESHOOTING.md`
3. **update_replication()** — Append entry to `REPLICATION-NOTES.md`
4. **open_issue()** — Create or update `ISSUE.md`
5. **halt_and_wait_human()** — Stop all work, await instruction

**No recovery attempts without human approval.**

---

## Ticket System

| Field | Description |
|-------|-------------|
| `depth` | 0=root, 1=worker, 2=leaf (NPU) |
| `parent` | Ticket ID of parent (null if root) |
| `children` | List of child ticket IDs |
| `status` | pending | escalated | closed |
| `attempts` | Number of execution attempts |
| `decrement` | Remaining escalation decrements |
| `priority` | low | medium | high | critical |
| `result` | Test pass/fail, score, and notes |

**Ticket Hierarchy:**
- Root ticket (depth 0) coordinates all work
- Worker tickets (depth 1) perform subtasks
- Leaf tickets (depth 2) run on NPU (lfm2.5-1.2B)

---

## Context Budget Rules

- At **60% utilization**: write `CHECKPOINT.md`
- At **80% utilization**: halt, alert human
- Never continue a task that cannot be completed

---

## Model Selection Policy

| Model | Depth | Slot | Purpose |
|-------|-------|------|---------|
| Qwen3-Coder-Next-GGUF | 0 | root | Orchestrator, high-level reasoning |
| Qwen3.5-35B-A3B-GGUF | 1 | worker | Subtask execution |
| lfm2.5-it-1.2b-FLM | 2 | leaf | NPU execution, fast leaf tasks |

**Model Pass Threshold:** 28/30 consecutive MT-01 test passes.

---

## Living Documents (Root)

| File | Purpose |
|------|---------|
| `TROUBLESHOOTING.md` | Append-only failure log |
| `REPLICATION-NOTES.md` | Environment setup, hardware notes |
| `ISSUE.md` | Open issue tracker |
| `SPEC.md` | Task specification (created per task) |
| `PLAN.md` | Agent plan (created per task) |
| `CHECKPOINT.md` | Mid-task state snapshot |

---

## Operator Rules

1. **Thinking Budget** — Use `<think>` blocks only in Plan phase; suppress in Build.
2. **Tool Calls** — One tool call at a time; wait for result.
3. **File Format** — All output must be Markdown+frontmatter or pure YAML.
4. **Phase Transitions** — No skipping or revisiting without human approval.
5. **Halt State** — No speculative fixes after halt; await human instruction.