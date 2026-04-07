# STEP-03 — Wire Registry into runner.py

> **AI-FIRST SPEC** — Vendor-agnostic. No model names. No endpoints.

---

## Goal

Replace the hardcoded `if/elif tool ==` dispatch block in `parse_and_run_tools()`
with a call to `registry.call(name, args)`. In the same pass, replace raw
`load_ticket` / `save_ticket` dict access with `ticket_io` typed wrappers
(Phase A migration — `as_dict()` shim preserves zero breakage).

---

## Luffy Law — Commit Protocol

> **Journal first, then push. Always.**
>
> Before every `git commit`, Luffy MUST:
> 1. Append a JSONL entry to `logs/luffy-journal.jsonl`
> 2. Stage the journal file: `git add logs/luffy-journal.jsonl`
> 3. Then commit everything together
>
> Journal entry schema:
> ```json
> {"ts": "ISO-8601", "step": "STEP-03-X", "action": "description", "status": "done", "files": ["list"]}
> ```

---

## Files to Modify / Create

| File | Action |
|---|---|
| `agent/runner.py` | Refactor `parse_and_run_tools()` + ticket load/save |
| `tests/test_runner_dispatch.py` | New — 10+ tests for dispatch and ticket-io wiring |

---

## Step 3-A: Refactor `parse_and_run_tools()`

### Current (hardcoded dispatch)

```python
if tool == "read_file":
    result = tool_read_file(path)
elif tool == "write_file":
    result = tool_write_file(path, content or "")
elif tool == "list_dir":
    result = tool_list_dir(path)
elif tool == "exec_python":
    result = tool_exec_python(path, timeout=exec_timeout)
else:
    result = f"ERROR: unknown tool: {tool}"
```

### Target (registry dispatch)

```python
from tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
from tools.terminal import run_command

REGISTRY = ToolRegistry()

# Register all tools once at module level
REGISTRY.register("read_file",   tool_read_file,   {"path": str})
REGISTRY.register("write_file",  tool_write_file,  {"path": str, "content": str})
REGISTRY.register("list_dir",    tool_list_dir,    {"path": str})
REGISTRY.register("exec_python", tool_exec_python, {"path": str})
REGISTRY.register("run_command", run_command,      {"cmd": list})
```

Inside `parse_and_run_tools()`:
```python
try:
    result = REGISTRY.call(tool, {"path": path, "content": content or "", "cmd": []})
except ToolNotFoundError as e:
    result = f"ERROR: {e}"
except ToolArgError as e:
    result = f"ERROR: {e}"
```

**Rules:**
- The `REGISTRY` object is instantiated once at module level — not inside the function
- `run_command` is now a registered tool; the parser already emits it via `TOOL: run_command PATH: ...`
  — no parser change needed
- `tool_exec_python`, `tool_read_file`, etc. remain in `runner.py` unchanged;
  registry wraps them, not replaces them

---

## Step 3-B: ticket_io Phase A Migration

Replace raw dict access in `execute_ticket()` with typed `Ticket` reads:

```python
from src.ticket_io import load_ticket_typed, as_dict

# In execute_ticket():
# OLD:
ticket    = load_ticket(ticket_path)
ticket_id = ticket.get("ticket_id", Path(ticket_path).stem)
depth     = int(ticket.get("depth", 0))

# NEW (Phase A — as_dict() shim means zero breakage downstream):
typed   = load_ticket_typed(ticket_path)     # returns Ticket dataclass
ticket  = as_dict(typed)                     # backward-compat shim
ticket_id = typed.ticket_id
depth     = typed.depth
```

`load_ticket_typed` and `as_dict` must be added to `src/ticket_io.py` if not
already present. They wrap the existing `load_ticket()` function.

**Rules:**
- `save_ticket` stays dict-based in Phase A — full typed save is Step 5
- `deps_met()` and `scan_open()` are unchanged
- All existing `ticket.get("field")` call-sites NOT in `execute_ticket()` are
  left for Step 5

---

## Validation Gate

```bash
python -m pytest tests/test_runner_dispatch.py -v
```

### Required Tests (minimum 10)

1. `test_registry_registered_tools` — all 5 tools registered after module import
2. `test_dispatch_read_file` — registry dispatches `read_file` and returns content
3. `test_dispatch_write_file` — registry dispatches `write_file`, file exists on disk
4. `test_dispatch_list_dir` — registry dispatches `list_dir`, returns directory listing
5. `test_dispatch_exec_python` — registry dispatches `exec_python`, parses returncode
6. `test_dispatch_run_command` — registry dispatches `run_command` with echo cmd
7. `test_dispatch_unknown_tool` — unknown tool name returns `ERROR:` string
8. `test_parse_and_run_tools_integration` — feed a multi-block response, verify all results
9. `test_typed_ticket_load` — `load_ticket_typed` returns Ticket with correct `ticket_id`
10. `test_typed_ticket_depth` — `typed.depth` returns int, not string
11. `test_as_dict_shim` — `as_dict(typed)` returns dict with all original keys

---

## Done Criteria

- [ ] All 11+ tests in `tests/test_runner_dispatch.py` pass
- [ ] `python -m pytest tests/ -v` — full suite passes (no regressions)
- [ ] `REGISTRY` is a module-level singleton in `runner.py`
- [ ] Journal entry written to `logs/luffy-journal.jsonl` **before** git commit
- [ ] Git commit message: `STEP-03: wire registry + ticket_io Phase A into runner.py`
