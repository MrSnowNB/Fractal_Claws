# STEP-04 — Trajectory Extractor

> **AI-FIRST SPEC** — Vendor-agnostic. No model names. No endpoints.

---

## Goal

Build `src/trajectory_extractor.py` — a post-run pass that reads
`logs/<ticket_id>-attempts.jsonl` for closed tickets, identifies winning
execution paths, and writes `skills/<goal-class>.yaml` with a compressed
toolpath. This is the self-improving loop: Cline reads `skills/` before
decomposing a new goal, skipping re-decomposition of known-good goal classes.

---

## Luffy Law — Commit Protocol

> **Journal first, then push. Always.**
>
> Before every `git commit`:
> 1. `pytest tests/` — all green
> 2. Append entry to `logs/luffy-journal.jsonl`
> 3. `git add <files> logs/luffy-journal.jsonl`
> 4. `git commit`
> 5. `git push`

---

## Files to Create

| File | Action |
|---|---|
| `src/trajectory_extractor.py` | New — core extractor module |
| `tests/test_trajectory.py` | New — 12+ tests |
| `skills/` | New directory — extractor writes skill YAML files here |

---

## Step 4-A: `src/trajectory_extractor.py`

### Module-level constants

```python
LOG_DIR    = "logs"
SKILLS_DIR = "skills"
CLOSED_DIR = "tickets/closed"
```

### Core function: `extract_trajectory(ticket_id: str) -> dict | None`

Reads `logs/<ticket_id>-attempts.jsonl`. Returns the winning attempt record
(first entry where `outcome == "pass"`), or `None` if no pass exists.

```python
def extract_trajectory(ticket_id: str) -> dict | None:
    log_path = os.path.join(LOG_DIR, f"{ticket_id}-attempts.jsonl")
    if not os.path.exists(log_path):
        return None
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("outcome") == "pass":
                return record
    return None
```

### Core function: `goal_class(ticket: dict) -> str`

Derives a slug from the ticket's `tags` list or `title` field.
Used as the filename stem for the skill YAML.

```python
def goal_class(ticket: dict) -> str:
    tags = ticket.get("tags") or []
    if tags:
        return "-".join(str(t).lower().replace(" ", "-") for t in tags[:3])
    title = ticket.get("title", ticket.get("ticket_id", "unknown"))
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:48]
```

### Core function: `write_skill(goal_cls: str, trajectory: dict, ticket: dict) -> str`

Writes `skills/<goal-class>.yaml`. Returns the path written.
If the file already exists, merges — keeps the best attempt (lowest `elapsed_s`).

```python
def write_skill(goal_cls: str, trajectory: dict, ticket: dict) -> str:
    os.makedirs(SKILLS_DIR, exist_ok=True)
    skill_path = os.path.join(SKILLS_DIR, f"{goal_cls}.yaml")
    skill = {
        "goal_class":   goal_cls,
        "ticket_id":    trajectory.get("ticket_id", ticket.get("ticket_id", "")),
        "tags":         ticket.get("tags", []),
        "tool_calls":   trajectory.get("tool_calls", 0),
        "tokens":       trajectory.get("tokens", 0),
        "elapsed_s":    trajectory.get("elapsed_s", 0),
        "tok_s":        trajectory.get("tok_s", 0),
        "finish":       trajectory.get("finish", ""),
        "attempt":      trajectory.get("attempt", 1),
        "ts":           trajectory.get("ts", ""),
        "produces":     ticket.get("produces", []),
        "consumes":     ticket.get("consumes", []),
    }
    if os.path.exists(skill_path):
        with open(skill_path, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
        if existing.get("elapsed_s", float("inf")) <= skill["elapsed_s"]:
            return skill_path  # existing is already better or equal
    with open(skill_path, "w", encoding="utf-8") as f:
        yaml.dump(skill, f, allow_unicode=True, sort_keys=False)
    return skill_path
```

### Core function: `run_extraction(closed_dir: str = CLOSED_DIR) -> list[str]`

Scans `tickets/closed/*.yaml`, calls `extract_trajectory` + `write_skill`
for each ticket that has a winning attempt. Returns list of skill paths written.

```python
def run_extraction(closed_dir: str = CLOSED_DIR) -> list[str]:
    written = []
    for ticket_path in sorted(glob.glob(os.path.join(closed_dir, "*.yaml"))):
        ticket = _load_ticket(ticket_path)
        tid = ticket.get("ticket_id", Path(ticket_path).stem)
        traj = extract_trajectory(tid)
        if traj is None:
            continue
        cls = goal_class(ticket)
        path = write_skill(cls, traj, ticket)
        written.append(path)
        print(f"[trajectory] {tid} → {path}")
    return written
```

### Helper: `_load_ticket(path: str) -> dict`

Same pattern as runner.py — handles single and multi-doc YAML.

### CLI entrypoint

```python
if __name__ == "__main__":
    paths = run_extraction()
    print(f"[trajectory] extracted {len(paths)} skill(s)")
    for p in paths:
        print(f"  {p}")
```

---

## Step 4-B: `tests/test_trajectory.py`

### Required Tests (minimum 12)

1. `test_extract_trajectory_pass` — write a JSONL with one pass record; assert returns it
2. `test_extract_trajectory_no_file` — nonexistent path returns None
3. `test_extract_trajectory_no_pass` — only fail records; returns None
4. `test_extract_trajectory_first_pass` — multiple records; returns FIRST pass
5. `test_extract_trajectory_skips_malformed` — malformed JSON line is skipped; valid pass returned
6. `test_goal_class_from_tags` — tags=["write", "python", "test"]; assert slug is "write-python-test"
7. `test_goal_class_from_title` — no tags, title="Generate Fibonacci"; assert slug is "generate-fibonacci"
8. `test_goal_class_max_length` — very long title; assert len(result) <= 48
9. `test_write_skill_creates_file` — call write_skill; assert YAML file exists with correct keys
10. `test_write_skill_keeps_best` — existing skill has lower elapsed_s; assert file unchanged
11. `test_write_skill_replaces_worse` — existing skill has higher elapsed_s; assert file updated
12. `test_run_extraction_integration` — create a closed ticket YAML + matching JSONL in tmp dirs;
    call run_extraction(closed_dir=tmp); assert skills file created with correct goal_class

**Platform notes:**
- All temp files: use `tmp_path` fixture
- `SKILLS_DIR` and `LOG_DIR` must be overrideable for tests (pass as args or monkeypatch)
- No network access, no model calls in any test

---

## Step 4-C: Gate Ticket

Same pattern as STEP-03-C:
1. Write journal entry to `logs/luffy-journal.jsonl` FIRST
2. Confirm `src/trajectory_extractor.py` and `tests/test_trajectory.py` exist and are non-empty
3. Write `logs/STEP-04-gate.txt` with status summary
4. Git commit: `STEP-04: trajectory extractor + 12 tests`

---

## Done Criteria

- [ ] All 12+ tests in `tests/test_trajectory.py` pass
- [ ] `python -m pytest tests/ -v` — full suite passes (no regressions)
- [ ] `python src/trajectory_extractor.py` runs without error on an empty closed dir
- [ ] `skills/` directory created on first run
- [ ] Journal entry written to `logs/luffy-journal.jsonl` **before** git commit
- [ ] Git commit message: `STEP-04: trajectory extractor + 12 tests`
