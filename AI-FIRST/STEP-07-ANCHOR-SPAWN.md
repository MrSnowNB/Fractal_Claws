# STEP-07 — Anchor Journal + TicketResult + Lint Gate + Delegate Spawn

> **AI-FIRST SPEC** — Read this fully before touching any file.
> All sub-tickets must be completed in order. Gate must be green before journal entry.

**Status:** ACTIVE  
**Depends on:** STEP-06 complete (skill-aware decomposition green)  
**Gate:** `pytest tests/ -v` → 167+ passed, 1 skipped, 0 failed + integration test passes manually  

---

## Why This Step Exists

Fractal Claws is a **message-passing architecture**. A ticket is not a file — it is
a typed message that can travel over any substrate: shared filesystem, pipe, socket,
LoRa radio, serial bus, or SMS. The parent (Key-Brain, 80B coder in Cline) decomposes
a goal and fires a ticket. The child (OpenClaw, A3B) picks it up, executes, and
fires a typed result back.

The ZBook is the **minimum viable two-node mesh**: one machine, two models, shared
filesystem as the transport layer. Once this step is done, swapping the filesystem
for LoRa serial is ~20 lines in `delegate_task()`.

### The shared-memory problem

On a ZBook running both models simultaneously:
- The 80B Key-Brain must sleep between dispatches so the A3B child has RAM to load
- Currently the Key-Brain re-reads 10–15 files on every cold start to reconstruct context
- This is the single biggest avoidable cost before any ticket is issued

The anchor journal (STEP-07-A) solves this: Key-Brain wakes → reads ONE JSON line
→ knows full system state → issues ticket → sleeps. The child loads, executes,
writes a typed TicketResult (including its own anchor summary), child exits.
Parent wakes on signal, reads anchor from result — zero file re-reads.

---

## Sub-Tickets (complete in order)

### STEP-07-A: Journal Anchor Schema

**Files:** `AI-FIRST/NEXT-STEPS.md`, `AI-FIRST/AGENT-PERSONA.md`, `agent/runner.py`  
**Gate:** Runner writes `anchor` field in journal entry on every commit path.

**What to build:**

1. Extend the journal entry schema in `AI-FIRST/NEXT-STEPS.md` Luffy Law section:

```json
{
  "ts": "ISO-8601",
  "step": "STEP-XX-Y",
  "action": "...",
  "status": "done",
  "files": [...],
  "anchor": {
    "system_state": "<one sentence: what is true about the system right now>",
    "open_invariants": ["<invariant 1>", "<invariant 2>"],
    "next_entry_point": "<STEP-XX-Y: what to do next and which file to touch first>"
  }
}
```

2. Add anchor-writing helper to `agent/runner.py` used in the journal append path.
   The runner already appends to `logs/luffy-journal.jsonl`. Extend it to
   include the `anchor` field when logging STEP completion events.

3. Enforce cold-start protocol in `AI-FIRST/AGENT-PERSONA.md`:
   > On cold start, read ONLY: (1) AI-FIRST/CONTEXT.md, (2) last line of
   > logs/luffy-journal.jsonl (anchor field), (3) current ticket's context_files.
   > Do NOT speculatively read any other file before issuing the first tool call.

**Invariant preserved:** Journal remains append-only. New entries are valid JSON + `\n`.

---

### STEP-07-B: TicketResult Dataclass

**Files:** `src/operator_v7.py`, `src/ticket_io.py`, `agent/runner.py`  
**Gate:** `pytest tests/ -v` still green after migration. `ticket.result` is typed everywhere.

**What to build:**

Add `TicketResult` to `src/operator_v7.py`:

```python
@dataclass
class TicketResult:
    """Typed return value from a ticket execution.

    Written by the child runner on pass/fail/error.
    Read by the parent runner for verification and chain-of-thought.
    Substrate-agnostic: serializes to/from dict for any transport.
    """
    outcome: str                          # "pass" | "fail" | "error"
    elapsed_s: float = 0.0
    tokens: int = 0
    tool_calls: int = 0
    artifact_paths: List[str] = field(default_factory=list)  # files the child produced
    reason: str = ""                      # pass/fail detail
    anchor: Dict[str, Any] = field(default_factory=dict)     # child's state summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "elapsed_s": self.elapsed_s,
            "tokens": self.tokens,
            "tool_calls": self.tool_calls,
            "artifact_paths": self.artifact_paths,
            "reason": self.reason,
            "anchor": self.anchor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TicketResult":
        return cls(
            outcome=data.get("outcome", "error"),
            elapsed_s=float(data.get("elapsed_s", 0.0)),
            tokens=int(data.get("tokens", 0)),
            tool_calls=int(data.get("tool_calls", 0)),
            artifact_paths=data.get("artifact_paths", []),
            reason=data.get("reason", ""),
            anchor=data.get("anchor", {}),
        )
```

Migrate `ticket.result` (currently `Dict[str, Any]`) to `Optional[TicketResult]`
in the `Ticket` dataclass. Update `to_dict()` / `from_dict()` in both
`operator_v7.py` and `ticket_io.py`. Update all write paths in `runner.py`
that currently assign to `ticket.result`.

**Invariant preserved:** Ticket round-trips through YAML without data loss.
`ticket.result` defaults to `None` for backward compat with existing YAML files.

---

### STEP-07-C: Ticket Lint Gate

**Files:** `src/ticket_io.py`, `tests/test_ticket_io.py`  
**Gate:** `pytest tests/test_ticket_io.py -v` green. Lint fires on malformed tickets.

**What to build:**

Add `lint_ticket(ticket: Ticket) -> List[str]` to `src/ticket_io.py`:

```python
import re as _re
import os as _os

def lint_ticket(ticket: Ticket) -> List[str]:
    """Pre-flight lint for a ticket before it leaves the parent's memory domain.

    Returns a list of violation strings. Empty list = clean.

    Rules:
      1. task references a .py filename but context_files is empty
      2. produces or consumes declared but context_files is empty
      3. context_files references a file that does not exist on disk
      4. task is None or empty string
    """
    errors = []
    task = ticket.task or ""

    # Rule 1
    file_refs = _re.findall(r'[\w./]+\.py', task)
    if file_refs and not ticket.context_files:
        errors.append(
            f"LINT-001: task references {file_refs} but context_files is empty. "
            f"Populate context_files before dispatching."
        )

    # Rule 2
    if (ticket.produces or ticket.consumes) and not ticket.context_files:
        errors.append(
            "LINT-002: produces/consumes declared but context_files is empty. "
            "Child cannot verify artifacts without knowing source files."
        )

    # Rule 3
    for cf in (ticket.context_files or []):
        if not _os.path.exists(cf):
            errors.append(f"LINT-003: context_files references missing file: {cf}")

    # Rule 4
    if not task.strip():
        errors.append("LINT-004: task is empty. Child has nothing to execute.")

    return errors
```

Call `lint_ticket()` inside `write_tickets()` in `runner.py`:
- **Warn** (print) on violations — do not block ticket write
- Log violations to `logs/lint-violations.jsonl` so the parent can review
- This is warn-not-block for now; escalate to hard-fail in STEP-08 once the
  lint rule set is battle-tested in real runs

Add 4+ tests to `tests/test_ticket_io.py` covering each lint rule.

**Why warn-not-block:** The child runner is A3B running cold. A lint violation
means the Key-Brain wrote a malformed ticket. We want to capture the violation
for review without halting the run — the child may still succeed if the task
is clear enough. Hard-fail comes after we measure false-positive rate in real runs.

---

### STEP-07-D: `delegate_task` Tool — Subprocess Spawn

**Files:** `tools/delegate_task.py` (new), `agent/runner.py`, `tools/registry.py`  
**Gate:** Integration test passes manually. See `tests/integration/test_delegate_task.py`.

**What to build:**

Create `tools/delegate_task.py`:

```python
"""
tools/delegate_task.py — Substrate-agnostic ticket dispatch.

Current transport: shared filesystem (ZBook POC).
  Parent writes ticket to tickets/open/<id>.yaml.
  Child runner polls tickets/open/ and picks it up.
  Parent waits for result_path to appear, then reads TicketResult.

Future transports (swap this module only):
  LoRa serial: serialize Ticket.to_dict() → JSON → write to serial port
  TCP socket:  JSON over localhost socket
  MQTT:        JSON message to broker topic
  SMS/LoRa:    encode to compact binary, send over radio

The Ticket schema and TicketResult schema do not change per transport.
Only the send/receive mechanism in this file changes.
"""
from __future__ import annotations
import json
import os
import time
from typing import Optional

from src.operator_v7 import Ticket, TicketResult
from src.ticket_io import save_ticket


OPEN_DIR    = "tickets/open"
CLOSED_DIR  = "tickets/closed"
FAILED_DIR  = "tickets/failed"
LOG_DIR     = "logs"


def delegate_task(
    ticket: Ticket,
    timeout: int = 300,
    poll_interval: float = 1.0,
) -> TicketResult:
    """Dispatch a ticket to the child runner and wait for a typed result.

    TRANSPORT: shared filesystem (ZBook POC)
      1. Write ticket to tickets/open/<id>.yaml
      2. Poll for result_path to appear (child writes on close)
      3. Read and return TicketResult from result_path
      4. Timeout → return TicketResult(outcome='error', reason='timeout')

    The child runner is always `agent/runner.py --once` — it picks up the
    next ready ticket from tickets/open/, executes it, and exits.
    The parent (Key-Brain) launched the child as a subprocess before calling
    this function, or the child is already running in a poll loop.
    """
    ticket_path = os.path.join(OPEN_DIR, f"{ticket.id}.yaml")
    result_path = ticket.result_path or os.path.join(LOG_DIR, f"{ticket.id}-result.txt")

    # Write ticket for child to pick up
    os.makedirs(OPEN_DIR, exist_ok=True)
    save_ticket(ticket_path, ticket)
    print(f"[delegate] ticket dispatched → {ticket_path}")

    # Poll for result
    deadline = time.time() + timeout
    closed_path = os.path.join(CLOSED_DIR, f"{ticket.id}.yaml")
    failed_path = os.path.join(FAILED_DIR, f"{ticket.id}.yaml")

    while time.time() < deadline:
        if os.path.exists(closed_path):
            print(f"[delegate] child closed ticket → {closed_path}")
            return _read_result(result_path, outcome="pass")
        if os.path.exists(failed_path):
            print(f"[delegate] child failed ticket → {failed_path}")
            return _read_result(result_path, outcome="fail")
        time.sleep(poll_interval)

    print(f"[delegate] timeout after {timeout}s — {ticket.id}")
    return TicketResult(
        outcome="error",
        reason=f"delegate_task timeout after {timeout}s",
    )


def _read_result(result_path: str, outcome: str) -> TicketResult:
    """Parse TicketResult from the result file written by the child."""
    if not os.path.exists(result_path):
        return TicketResult(outcome=outcome, reason="result_path not found")
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Extract key fields from the result file written by _write_result() in runner.py
    tokens = _extract_int(content, "tokens:")
    elapsed = _extract_float(content, "elapsed:")
    tool_calls = len([l for l in content.splitlines() if l.startswith("[")])
    return TicketResult(
        outcome=outcome,
        elapsed_s=elapsed,
        tokens=tokens,
        tool_calls=tool_calls,
        artifact_paths=[result_path],
        reason=_extract_str(content, "reason:"),
    )


def _extract_int(text: str, key: str) -> int:
    for line in text.splitlines():
        if line.startswith(key):
            try: return int(line.split(":", 1)[1].strip())
            except ValueError: pass
    return 0

def _extract_float(text: str, key: str) -> float:
    for line in text.splitlines():
        if line.startswith(key):
            try: return float(line.split(":", 1)[1].strip().rstrip("s"))
            except ValueError: pass
    return 0.0

def _extract_str(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(key):
            return line.split(":", 1)[1].strip()
    return ""
```

Register in `agent/runner.py`:
```python
from tools.delegate_task import delegate_task as _delegate_task
REGISTRY.register("delegate_task", _delegate_task, {
    "ticket": {"type": dict},
    "timeout": {"type": int, "required": False, "default": 300},
})
```

---

### STEP-07-E: Integration Test (Manual)

**File:** `tests/integration/test_delegate_task.py`  
**Gate:** Skipped by default (`pytest.mark.skip`). Run manually on ZBook.

```python
"""
Integration test: parent dispatches a ticket, child runner closes it.

RUN MANUALLY ON ZBOOK:
  pytest tests/integration/test_delegate_task.py -v -s

Requires:
  - LM Studio or Lemonade serving the A3B model
  - settings.yaml configured
  - Both runner instances on the same filesystem
"""
import pytest
# All tests in this file are skipped in CI / automated gate runs
pytestmark = pytest.mark.skip(reason="Integration test — run manually on ZBook with model loaded")

def test_delegate_task_roundtrip(tmp_path):
    """Parent writes ticket, child closes it, parent reads TicketResult."""
    # ... implementation here at STEP-07-E time
    pass
```

---

### STEP-07-F: Gate, Journal (with Anchor), Commit, Push

1. `pytest tests/ -v` → 167+ passed, 1 skipped, 0 failed
2. Append journal entry WITH anchor field:
```json
{
  "ts": "<ISO-8601>",
  "step": "STEP-07-F",
  "action": "Anchor journal + TicketResult + Lint gate + delegate_task tool complete",
  "status": "done",
  "files": [
    "src/operator_v7.py",
    "src/ticket_io.py",
    "agent/runner.py",
    "tools/delegate_task.py",
    "AI-FIRST/AGENT-PERSONA.md",
    "tests/test_ticket_io.py",
    "tests/integration/test_delegate_task.py"
  ],
  "anchor": {
    "system_state": "TicketResult typed, lint gate active, delegate_task in REGISTRY, anchor journal protocol enforced",
    "open_invariants": [
      "Ticket round-trips YAML without data loss",
      "Journal is append-only valid JSON",
      "context_files lint warns on violation",
      "delegate_task waits for child result before returning"
    ],
    "next_entry_point": "STEP-08-A: hard-fail lint gate after measuring false-positive rate, then child process spawn with real A3B model"
  }
}
```
3. `git commit -m "STEP-07-F: Anchor+TicketResult+Lint+Delegate complete"`
4. `git push`
5. Mark STEP-07 `[x] DONE` in `AI-FIRST/NEXT-STEPS.md`

---

## Architecture Note — The Substrate Abstraction

The ZBook POC uses shared filesystem. The table below shows how `delegate_task()`
changes per substrate — everything else stays identical:

| Transport | `delegate_task()` change | Ticket format |
|---|---|---|
| Shared filesystem (ZBook POC) | Write YAML, poll for close | YAML file |
| TCP localhost socket | Send JSON, receive JSON | JSON string |
| LoRa serial (Liberty Mesh) | Write to serial port, read response | Compact JSON or binary |
| MQTT broker | Publish to topic, subscribe to result | JSON payload |
| SMS / Meshtastic | Encode to short JSON, send via API | Compressed JSON |

The `Ticket.to_dict()` / `TicketResult.from_dict()` round-trip is the contract.
The substrate is the wire. The wire does not change the message.

---

## Files Modified in This Step

| File | Change |
|---|---|
| `src/operator_v7.py` | Add `TicketResult` dataclass; migrate `ticket.result` type |
| `src/ticket_io.py` | Add `lint_ticket()` function |
| `agent/runner.py` | Anchor journal writes; call `lint_ticket()`; register `delegate_task` |
| `tools/delegate_task.py` | New — substrate-agnostic ticket dispatch |
| `AI-FIRST/AGENT-PERSONA.md` | Add cold-start context discipline rule |
| `AI-FIRST/NEXT-STEPS.md` | Journal schema update + Step 7 marked active |
| `tests/test_ticket_io.py` | 4+ new lint gate tests |
| `tests/integration/test_delegate_task.py` | New — skipped by default, manual ZBook run |
| `logs/luffy-journal.jsonl` | New entries with `anchor` field |
| `logs/lint-violations.jsonl` | New — created on first lint violation |

---

*Spec written: 2026-04-08*  
*Author: Mark Snow + Luffy*  
*Delete when: STEP-07-F committed and pushed*
