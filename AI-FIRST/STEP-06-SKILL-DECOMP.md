# Step 6 — Skill-Aware Decomposition

> **AI-FIRST SPEC** — Read `AI-FIRST/CONTEXT.md` before this file.
> This spec is self-contained. Follow it ticket by ticket in order.
> Do not start a ticket until its dependency (if any) is closed.

---

## Goal

Close the trajectory-extractor loop. Step 4 writes `skills/<goal-class>.yaml`
after every successful run. Step 6 reads those files before decomposing a goal.

If a matching skill exists → skip LLM decomposition, run the cached toolpath directly.
If no match → decompose as normal, write a new skill on success.

This makes the runner progressively faster on repeated goal classes — it learns.

**Why this matters (first principles):**
Decomposition is the most expensive step: it requires an LLM call, token budget,
and latency. A cached toolpath that has already passed the gate is provably correct
for that goal class. Reusing it is not a shortcut — it is the rational choice.

---

## Invariants This Step Must Preserve

1. `pytest tests/ -v` — full suite green before and after every commit
2. `logs/luffy-journal.jsonl` — valid JSONL, one entry per commit
3. All existing ticket lifecycle behavior (open → in_progress → closed/failed)
4. `REGISTRY.call()` dispatch — not reverted
5. Typed `Ticket` field access in runner — not reverted to dict access
6. Trajectory extractor writes — not broken by new skill reads
7. No hardcoded model names introduced
8. `tests/integration/` tests remain skipped by default

**If any invariant is at risk, stop. Document in TROUBLESHOOTING.md. Ask.**

---

## Tickets

### STEP-06-A: Write src/skill_store.py

```yaml
ticket_id: STEP-06-A
task: >
  Create src/skill_store.py with three public functions:

  1. load_skill(goal_class: str, skills_dir: str = "skills") -> Optional[dict]
     - Reads skills/<goal_class>.yaml if it exists
     - Returns the parsed dict, or None if no file found
     - Fuzzy match: if exact file not found, scan skills/ for any filename
       whose stem has Levenshtein distance <= 2 from goal_class
     - Raises SkillLoadError (custom exception) if YAML is malformed

  2. write_skill(goal_class: str, skill: dict, skills_dir: str = "skills") -> None
     - Writes skills/<goal_class>.yaml (creates skills/ if absent)
     - Validates that skill dict contains keys: goal_class, tool_sequence, elapsed_s
     - Raises SkillWriteError if validation fails

  3. match_goal_class(ticket_task: str, skills_dir: str = "skills") -> Optional[str]
     - Tokenizes ticket_task to extract a goal_class string
     - Returns the best matching skill filename stem (or None)
     - Exact match preferred; fuzzy (distance <= 2) as fallback

  Custom exceptions: SkillLoadError, SkillWriteError (both subclass RuntimeError)
depends_on: []
gate: >
  src/skill_store.py exists.
  python -c "from src.skill_store import load_skill, write_skill, match_goal_class; print('OK')"
  exits 0.
```

**Implementation notes:**
- Levenshtein distance: implement a simple 2D DP version inline (no external dep)
- YAML round-trip: use `yaml.safe_load` / `yaml.safe_dump` — no custom tags
- `skills/` directory path must be configurable (default relative to CWD)
- All functions must be pure (no global state, no side effects beyond file I/O)

---

### STEP-06-B: Wire skill_store into runner.py decomposition path

```yaml
ticket_id: STEP-06-B
task: >
  In agent/runner.py, add a skill cache check before the decompose() call:

  1. Import skill_store from src.skill_store
  2. In the ticket execution path, before calling decompose(ticket):
     a. Call match_goal_class(ticket.task) to get a candidate goal_class
     b. If candidate found, call load_skill(candidate)
     c. If skill loaded: log cache hit to audit JSONL with source="skill_cache",
        run the cached tool_sequence directly via REGISTRY.call(), skip decompose()
     d. If no skill or no match: fall through to decompose() as normal
  3. After a successful run (outcome=pass), call write_skill() with the
     executed tool_sequence, elapsed time, and goal_class

  The decompose() function must NOT be called when a skill cache hit occurs.
  The audit JSONL entry for a cache-hit ticket must include:
    {"source": "skill_cache", "goal_class": "<matched>", "cache_hit": true}
depends_on: [STEP-06-A]
gate: >
  pytest tests/ -v — all green.
  Manual trace: a ticket whose task matches an existing skill file must produce
  a cache-hit audit entry and must not call decompose().
```

**What to watch for:**
- `ticket.task` may be None for legacy tickets — guard with `if ticket.task`
- Cache hit logging must append to the existing audit JSONL, not overwrite
- `write_skill()` must only be called on `outcome=pass`, not on failure
- Do not break the existing `drain()` loop or deadlock detection

---

### STEP-06-C: Write tests/test_skill_decomp.py

```yaml
ticket_id: STEP-06-C
task: >
  Write tests/test_skill_decomp.py covering:

  Unit tests (skill_store module):
    1. test_load_skill_returns_none_when_missing — no file → None
    2. test_load_skill_returns_dict_when_present — valid YAML → dict
    3. test_load_skill_raises_on_malformed_yaml — bad YAML → SkillLoadError
    4. test_write_skill_creates_file — write → file exists, content round-trips
    5. test_write_skill_raises_on_missing_keys — incomplete dict → SkillWriteError
    6. test_match_goal_class_exact — exact stem match → returns stem
    7. test_match_goal_class_fuzzy — distance-2 stem → returns stem
    8. test_match_goal_class_no_match — no file within distance 2 → None

  E2E cache-hit test:
    9. test_skill_cache_hit_skips_decompose:
         - Write a skill YAML to a tmp skills/ dir
         - Create a ticket whose task matches the skill's goal_class exactly
         - Run the ticket through the runner with a mock decompose()
         - Assert decompose() was NOT called
         - Assert audit JSONL contains cache_hit=true entry

  All tests must be self-contained (tmp dirs, no real skills/ dir mutation).
  Use pytest tmp_path fixture for all file I/O.
depends_on: [STEP-06-B]
gate: pytest tests/test_skill_decomp.py -v — all 9 tests green
```

---

### STEP-06-D: Gate, Journal, Commit

```yaml
ticket_id: STEP-06-D
task: >
  Run the full gate sequence:
    1. pytest tests/ -v — all green
    2. pytest tests/test_skill_decomp.py -v — all 9 green
    3. Confirm skill cache hit path is exercised (E2E test passes)
  Write gate summary to logs/STEP-06-gate.txt:
    - Full test count and pass rate
    - Skill store functions verified (load, write, match)
    - Cache hit path confirmed by E2E test
    - Any new optional fields added to Ticket or runner
  Append journal entry to logs/luffy-journal.jsonl.
  git add src/skill_store.py agent/runner.py tests/test_skill_decomp.py \
           logs/STEP-06-gate.txt logs/luffy-journal.jsonl
  git commit -m "STEP-06: skill-aware decomposition — cache hit skips LLM call"
  git push
depends_on: [STEP-06-C]
gate: git push succeeds, journal valid, all tests green
```

---

## Validation Gate (Final)

```bash
# 1. Full test suite
pytest tests/ -v
# Expected: all green (151+ tests)

# 2. Skill decomp suite
pytest tests/test_skill_decomp.py -v
# Expected: 9/9 green

# 3. Skill store importable
python -c "from src.skill_store import load_skill, write_skill, match_goal_class; print('OK')"

# 4. Journal valid
python -c "
import json
for i, line in enumerate(open('logs/luffy-journal.jsonl'), 1):
    line = line.strip()
    if line: json.loads(line)
print('Journal: all lines valid')
"

# 5. Gate file present
test -f logs/STEP-06-gate.txt && echo 'Gate file: present'
```

All five checks must pass before Step 6 is marked DONE.

---

## Architecture Impact

After this step, the runner decision tree is:

```
Ticket received
  └─ ticket.task exists?
       ├─ YES → match_goal_class(ticket.task)
       │          ├─ MATCH → load_skill() → run tool_sequence → log cache_hit
       │          └─ NO MATCH → decompose() → run → write_skill() on pass
       └─ NO  → decompose() → run → write_skill() on pass
```

This is the minimal change that closes the trajectory loop. Step 7 adds
child-process spawning (OpenClaw) on top of this stable routing layer.

---

## Step 7 Preview (Do Not Build Yet)

Once skill-aware routing is stable:
- **Typed TicketResult** — `ticket.result` raw dict replaced with `TicketResult` dataclass
- **OpenClaw spawn** — `delegate_task` tool triggers child runner on second GPU at depth=1
- **Multi-agent audit** — parent and child audit logs merged into unified JSONL

---

*Spec version: 1.0*  
*Written: 2026-04-08*  
*Maintained by: Mark Snow + Luffy*
