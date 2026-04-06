---
title: src/operator_v7.py — Self-Healing Recursive First Principles Operator
version: "0.7.0"
last_updated: "2026-04-05"
---

# Self-Healing Recursive First Principles Operator v7

## Overview

This module implements the core operator functionality for the Fractal_Claws project.

## Features

- **First Principles Thinking**: Break down problems to fundamental truths
- **Recursive Decomposition**: Decompose complex tasks into atomic subtasks
- **Self-Healing**: Trigger failure procedure on any failure or uncertainty
- **Ticket System**: Coordinate work using a hierarchical ticket system

## Core Classes

### Operator

The main operator class that coordinates all work.

#### Methods

- `__init__()`: Initialize the operator
- `process_ticket(ticket)`: Process a ticket through the lifecycle
- `decompose_task(task)`: Decompose a task into atomic subtasks
- `handle_failure(ticket, error)`: Trigger the 5-step failure procedure
- `validate(ticket)`: Run validation gates

### Ticket

A unit of work with pass/fail criteria.

#### Attributes

- `id`: Unique identifier
- `depth`: 0 (root), 1 (worker), 2 (leaf)
- `parent`: Parent ticket ID
- `children`: List of child ticket IDs
- `status`: pending | escalated | closed
- `attempts`: Number of execution attempts
- `decrement`: Remaining escalation decrements
- `priority`: low | medium | high | critical
- `result`: Test pass/fail, score, and notes

## Lifecycle

1. **Plan**: Write SPEC.md and PLAN.md
2. **Build**: Implement the spec
3. **Validate**: Run all validation gates
4. **Review**: Human reviews the diff
5. **Release**: Tag and document the artifact

## Validation Gates

All four gates must be green before progression:

| Gate | Command | Pass Condition |
|------|---------|----------------|
| Unit | `pytest -q` | 0 failed, 0 errors |
| Lint | `ruff check .` | clean output |
| Type | `mypy .` | 0 errors |
| Docs | `spec drift check` | no unresolved drift |

## Failure Procedure

On any failure or uncertainty:

1. **capture_logs()**: Save full stdout/stderr
2. **update_troubleshooting()**: Append to TROUBLESHOOTING.md
3. **update_replication()**: Append to REPLICATION-NOTES.md
4. **open_issue()**: Create or update ISSUE.md
5. **halt_and_wait_human()**: Stop all work, await instruction

## Usage

```python
from src.operator_v7 import Operator, Ticket

# Initialize operator
operator = Operator()

# Create a root ticket
ticket = Ticket(
    id="TKT-2026-04-05-001",
    depth=0,
    priority="high",
)

# Process the ticket
operator.process_ticket(ticket)
```

## Model Selection

| Model | Depth | Slot | Purpose |
|-------|-------|------|---------|
| Qwen3-Coder-Next-GGUF | 0 | root | Orchestrator, high-level reasoning |
| Qwen3.5-35B-A3B-GGUF | 1 | worker | Subtask execution |
| lfm2.5-it-1.2b-FLM | 2 | leaf | NPU execution, fast leaf tasks |

**Model Pass Threshold**: 28/30 consecutive MT-01 test passes.