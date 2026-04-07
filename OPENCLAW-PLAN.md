---
title: OpenClaw Integration Plan
version: "0.1.0"
created: "2026-04-07"
status: DRAFT — pending review
---

# OPENCLAW-PLAN.md
## Integration Plan: OpenClaw Tool Layer + Daemon + Memory

> This document is the architectural contract for the next phase of Fractal Claws development.
> It is written after the first successful end-to-end run (TS-20260407-001).
> The proof gate passed. The bud is proven. Growth may now begin.

---

## Context: What We Have Now

After the v3 fixes committed today, the harness state is:

| Component | Status | Notes |
|---|---|---|
| `pre_flight.py` | ✅ Fixed | 3-step probe: list → generation → READY |
| `runner.py` | ✅ Fixed | Unified 80% budget policy, removed OUTPUT_RATIO drift |
| `settings.yaml` | ✅ Fixed | Budget fields consistent, comments clarify CAP vs CEILING |
| `.gitignore` | ✅ Fixed | Agent artifacts excluded, closed tickets kept |
| `memory/solved/` | ❌ Missing | Directory exists in VISION but not yet implemented |
| `memory/failures/` | ❌ Missing | Failure promotion not yet wired |
| `daemon/` | ❌ Missing | Pure-witness filesystem watcher not yet built |
| `tools/` | ⚠️ Partial | `spec_check.py` referenced in settings but no tool registry |
| `LESSONS_LEARNED.md` | ❌ Missing | Required by VISION — must be created |

**The OpenClaw layer is the bridge between the working proof-of-concept and the full
VISION architecture.** It is the set of components that, when added, complete the
three-layer model from VISION.md §2.1.

---

## Phase 1 — Memory Layer (Week 1)

### Goal
Wire the closed ticket → memory promotion pipeline so the system actually learns
from completed runs rather than starting fresh every time.

### Deliverables

**1.1 `memory/` directory structure**
```
memory/
  solved/       # promoted closed tickets (YAML, renamed by goal hash)
  failures/     # one-line failure records appended per failed ticket
  tools/        # usage frequency per tool (JSON, updated after each run)
  .gitkeep files in each
```

**1.2 `agent/consolidate.py`** — post-run promotion script
- Reads all tickets in `tickets/closed/`
- For each closed ticket with `status: closed` and a valid result_path:
  - Hashes `task` field (SHA256 truncated to 12 chars) → filename
  - Writes to `memory/solved/{hash}-{ticket_id}.yaml`
  - Includes: task, tool_calls_used, depth_at_close, elapsed, tok_s
- Reads all tickets in `tickets/failed/`
- Appends one line per failure to `memory/failures/failures.log`:
  `{date} | {ticket_id} | {task[:60]} | {reason}`
- Updates `memory/tools/usage.json` with tool call frequency counts
- Called automatically by runner.py after `drain()` completes

**1.3 `agent/memory_lookup.py`** — goal-to-solved-path matcher
- Takes a goal string
- Fuzzy-matches against `task` fields in `memory/solved/`
- Returns the best matching solved path if similarity > 0.85 (configurable)
- Used by `main()` before calling `decompose_goal()`
- Simple: TF-IDF cosine similarity on task strings, no embeddings

**1.4 `LESSONS_LEARNED.md`** — seed with current lessons
- Format per VISION §4.2
- Seed entries:
  - 4B empty choices root cause (TS-20260406-001)
  - max_tokens as output cap vs input budget confusion
  - documentation ambiguity causing agent thrash (TS-20260407-004)
  - decompose_budget missing from config

### Integration Point in runner.py
```python
# In main(), before decompose_goal():
from agent.memory_lookup import find_solved_path
match = find_solved_path(goal)
if match:
    print(f"[runner] memory hit: replaying {match['source']}")
    write_tickets(match['tickets'])
else:
    tickets = decompose_goal(goal, first_n)

# After drain() completes:
from agent.consolidate import consolidate
consolidate()
```

---

## Phase 2 — Daemon (Week 1-2)

### Goal
Build the pure-witness filesystem watcher per VISION §2.5.
The daemon has zero authority. It observes and reports only.

### Deliverables

**2.1 `daemon/watcher.py`** — filesystem observer
- Watches: `tickets/open/`, `tickets/closed/`, `tickets/failed/`, `locks/`
- Emits one-line status reports every N seconds (configurable, default 10s)
- Report format:
  ```
  [daemon] 2026-04-07T11:00:00 | open=3 closed=12 failed=1 | agent=ALIVE | elapsed=47s
  ```
- Writes to `logs/daemon_{date}.log`
- Does NOT restart bud on failure. Does NOT requeue tickets. Does NOT alert.
- Exits cleanly when `locks/agent.lock` is deleted (bud died)

**2.2 `locks/` directory + lockfile protocol**
- `runner.py` creates `locks/agent.lock` on startup with PID and timestamp
- `runner.py` deletes `locks/agent.lock` on clean exit
- `daemon/watcher.py` monitors the lock file to know if a bud is alive
- Lock format:
  ```json
  {"pid": 12345, "started": "2026-04-07T11:00:00", "goal": "...(first 80 chars)"}
  ```

**2.3 Add lockfile creation/deletion to runner.py**
```python
# In main(), before prewarm():
import atexit
lock_path = "locks/agent.lock"
os.makedirs("locks", exist_ok=True)
with open(lock_path, "w") as f:
    json.dump({"pid": os.getpid(),
               "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "goal": (goal or "drain")[:80]}, f)
atexit.register(lambda: os.path.exists(lock_path) and os.remove(lock_path))
```

---

## Phase 3 — OpenClaw Tool Layer (Week 2-3)

### Goal
Formalize the tool registry so new tools can be added with evidence tracking,
and OpenClaw-specific tools can plug in cleanly.

### What Is OpenClaw?
OpenClaw is the **tool abstraction layer** — the interface between runner.py's
tool dispatch system and the physical capabilities of the system.
Currently, tools are hardcoded as `tool_read_file()`, `tool_write_file()`, etc.
OpenClaw turns these into a registry with:
- Evidence tracking (which tickets earned this tool)
- Schema validation (correct invocation syntax)
- Permission checking (allowed_tools per ticket)
- Future: remote tool dispatch (HTTP, subprocess, MCP)

### Deliverables

**3.1 `tools/registry.py`** — tool registry
```python
# Tool entry structure:
{
  "name": "read_file",
  "handler": tool_read_file,
  "description": "Read a file from the local filesystem",
  "args": ["path"],
  "earned_by": ["TASK-001", "TASK-005", "TASK-012"],  # evidence tickets
  "call_count": 47,
  "last_used": "2026-04-07T11:00:00"
}
```
- `REGISTRY: dict[str, ToolEntry]`
- `register(name, handler, description, args)` — adds tool to registry
- `dispatch(tool_name, **kwargs)` — routes call through registry
- `check_permission(tool_name, allowed_tools: list)` — ticket permission gate
- Loaded by runner.py at startup; replaces the current if/elif tool dispatch

**3.2 `tools/base_tools.py`** — extract current hardcoded tools
- Move `tool_read_file`, `tool_write_file`, `tool_list_dir`, `tool_exec_python`
  out of runner.py and into `tools/base_tools.py`
- Each tool registers itself on import
- runner.py imports `from tools.registry import dispatch, check_permission`

**3.3 `tools/evidence.py`** — tool evidence tracker
- After each closed ticket, records which tools were called
- Increments `call_count` and `last_used` in registry
- When a tool reaches `call_count >= 3` AND `earned_by` has 3+ unique tickets,
  it is marked `status: proven` in `memory/tools/usage.json`
- This is the enforcement of VISION Rule 5

**3.4 New tools (earned, not anticipated)**
The following tools have been earned by evidence from the first successful run
and should be registered once the registry is built:

| Tool | Evidence | Status |
|---|---|---|
| `read_file` | TASK-015 through TASK-022 (8 uses) | ✅ Proven |
| `write_file` | TASK-015 through TASK-022 (8 uses) | ✅ Proven |
| `exec_python` | TASK-015 through TASK-022 (6 uses) | ✅ Proven |
| `list_dir` | TASK-015 through TASK-022 (2 uses) | ⚠️ 2 of 3 needed |

No new tools are added until evidence is collected from more runs.
The `http_get` tool is NOT added yet — zero evidence from production runs.

---

## Phase 4 — Harder Test Goals (Week 2)

Now that the base harness is proven, the next test goals must exercise:
1. **Multi-level `depends_on` chains** — at least 3 levels deep
2. **Retry/depth increment** — at least one ticket must fail on first attempt
3. **File dependency passing** — upstream results injected into downstream context
4. **Memory lookup** — re-run a previously solved goal and confirm it hits memory

### Candidate Test Goal v2:
```
python agent/runner.py --goal "create a CSV of the first 50 prime numbers with
columns: index, prime, is_mersenne. Save to output/primes.csv. Then read it back
and verify row count is exactly 50 and all values in the prime column are actually prime."
```
This goal requires:
- Write script to generate primes (TASK-N)
- Exec script → output/primes.csv (TASK-N+1, depends_on N)
- Read back and validate row count (TASK-N+2, depends_on N+1)
- Validate primality of each value (TASK-N+3, depends_on N+2)

After this passes, re-run the same goal → should hit `memory/solved/` and skip decompose.

### Candidate Test Goal v3 (stress test):
```
python agent/runner.py --goal "write a Python class in output/matrix.py that implements
a 2D matrix with add, multiply, and transpose methods. Write pytest tests in output/test_matrix.py.
Run the tests and report pass/fail. If any test fails, fix the class and re-run."
```
This goal exercises the retry loop — the agent must self-correct a failing test.

---

## Phase 5 — Clone Protocol (Week 3)

Once memory, daemon, and tool registry are proven, formalize the clone procedure:

**5.1 `tools/clone.py`** — bud cloning script
```bash
python tools/clone.py --name "my_new_bot" --mission "summarize research papers"
```
- Copies the full repo
- Clears `tickets/open/`, `tickets/failed/`, `output/`, `logs/`
- Preserves `memory/solved/`, `memory/failures/`, `memory/tools/`
- Writes the mission into a `MISSION.md` file in the new clone
- Runs the proof gate (`pre_flight.py` + hello world ticket)
- Reports success/failure

**5.2 `REPLICATION-NOTES.md` update**
- Document the clone procedure
- Document what memory travels and what is cleared
- Document the proof gate requirement before first mission

---

## Implementation Order

Do these in strict sequence. Do not start Phase N+1 until Phase N passes the proof gate.

```
[✅ DONE]  v3 fixes: budget, pre_flight probe, .gitignore
[ ]  Phase 1: memory/ structure + consolidate.py + memory_lookup.py + LESSONS_LEARNED.md
[ ]  Phase 2: daemon/watcher.py + locks/ protocol + runner.py lockfile
[ ]  Phase 3: tools/registry.py + base_tools.py + evidence.py
[ ]  Phase 4: Run test goal v2 (primes CSV). Run test goal v3 (matrix class + pytest).
[ ]  Phase 5: clone.py + REPLICATION-NOTES.md update
```

**Proof gate at each phase boundary:**
```bash
python pre_flight.py
python init.py "write hello world to output/test.txt and verify the file exists"
```
Both must pass before the next phase begins.

---

## What OpenClaw Is NOT

- It is NOT a new agent framework. runner.py stays the executor.
- It is NOT an external service. Everything runs local.
- It is NOT a plugin system. Tools are Python functions in `tools/`.
- It is NOT a breaking change. Phase 3 refactors existing tools without changing behavior.
- It is NOT LangChain, AutoGen, or any existing framework. This is first-principles.

---

*Written 2026-04-07. Append as phases complete. Never delete.*
*— Mark Snow / GarageAGI*
