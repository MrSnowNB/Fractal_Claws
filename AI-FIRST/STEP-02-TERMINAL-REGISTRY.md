# Step 2: Terminal Tool + Tool Registry

> **AI-FIRST SPEC** — Source of truth for `tools/terminal.py` and `tools/registry.py`.
> Read this entire file before writing a single line of code.

---

## Mandatory Logging Rule (LUFFY LAW)

> **Every action Luffy takes must be logged to `logs/luffy-journal.jsonl`
> BEFORE the action executes and AFTER it completes, with a timestamp.
> This applies even on re-runs, even if the file already exists, even if
> the test was already green. There are no exceptions.**

Every log entry must include:
```json
{
  "timestamp": "2026-04-07T22:15:00",
  "ticket_id": "TASK-XXX",
  "step": "<what step within the ticket>",
  "action": "<what Luffy is about to do or just did>",
  "status": "start | pass | fail | skip",
  "detail": "<any relevant output, error, or note>"
}
```

Use `scripts/append_jsonl.py` (Toolbox T06) for every entry.
Log at minimum: ticket start, each tool call, each test run, each fix attempt, final result.

---

## What This Step Builds

### `tools/terminal.py`
A sandboxed subprocess executor. Gives the agent controlled shell access.

```python
# Minimum public interface:
from tools.terminal import run_command

result = run_command(
    cmd=["git", "log", "--oneline", "-5"],
    timeout=30,           # seconds, default 30
    cwd=None,             # working directory, default repo root
    allowed_paths=None,   # restrict file args to these dirs
)
# Returns:
# {
#   "stdout": str,
#   "stderr": str,
#   "returncode": int,
#   "timed_out": bool,
#   "blocked": bool,     # True if a DANGEROUS_PATTERN matched
#   "elapsed_ms": int,
# }
```

**DANGEROUS_PATTERNS denylist** — these substrings in any arg block execution:
```python
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=/dev/zero",
    ":(){ :|:& };",   # fork bomb
    "> /dev/sda",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
]
```

If any pattern matches (case-insensitive, substring), return immediately with
`{"blocked": True, "returncode": -1, "stdout": "", "stderr": "blocked by denylist", "timed_out": False}`.

**Timeout enforcement:** Use `subprocess.run(..., timeout=timeout)`. On `TimeoutExpired`,
return `{"timed_out": True, "returncode": -1, "stdout": "", "stderr": "timed out", "blocked": False}`.

---

### `tools/registry.py`
Maps tool name strings → callables + validates args against schema.

```python
# Minimum public interface:
from tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register("run_command", run_command, schema={
    "cmd": {"type": list, "required": True},
    "timeout": {"type": int, "required": False, "default": 30},
    "cwd": {"type": str, "required": False, "default": None},
})

result = registry.call("run_command", {"cmd": ["echo", "hello"]})
# Returns the tool's return value directly.

# Raises ToolNotFoundError if name not registered.
# Raises ToolArgError if required arg missing or wrong type.
```

**Schema validation rules:**
- Missing required arg → raise `ToolArgError`
- Wrong type → raise `ToolArgError`
- Missing optional arg → fill with `default` value
- Extra args not in schema → silently pass through (forward-compatible)

**Errors to define in `tools/registry.py`:**
```python
class ToolNotFoundError(Exception): ...
class ToolArgError(Exception): ...
```

---

## File Layout

```
tools/
  __init__.py       # empty
  terminal.py       # run_command + DANGEROUS_PATTERNS + TOOL_SCHEMA
  registry.py       # ToolRegistry + ToolNotFoundError + ToolArgError
tests/
  test_tools.py     # validation gate (see below)
```

---

## Validation Gate

File: `tests/test_tools.py`

```python
# tests/test_tools.py
import pytest
from tools.terminal import run_command
from tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError

# --- terminal.py tests ---

def test_run_command_basic():
    r = run_command(["echo", "hello"])
    assert r["returncode"] == 0
    assert "hello" in r["stdout"]
    assert r["blocked"] is False
    assert r["timed_out"] is False

def test_run_command_nonzero():
    r = run_command(["python", "-c", "import sys; sys.exit(42)"])
    assert r["returncode"] == 42

def test_run_command_stderr():
    r = run_command(["python", "-c", "import sys; sys.stderr.write('err\\n')"])
    assert "err" in r["stderr"]

def test_run_command_timeout():
    r = run_command(["python", "-c", "import time; time.sleep(10)"], timeout=1)
    assert r["timed_out"] is True
    assert r["returncode"] == -1

def test_run_command_blocked():
    r = run_command(["bash", "-c", "rm -rf /"])
    assert r["blocked"] is True
    assert r["returncode"] == -1

def test_run_command_elapsed_ms():
    r = run_command(["echo", "hi"])
    assert isinstance(r["elapsed_ms"], int)
    assert r["elapsed_ms"] >= 0

def test_run_command_cwd(tmp_path):
    r = run_command(["pwd"], cwd=str(tmp_path))
    assert str(tmp_path) in r["stdout"]

# --- registry.py tests ---

def test_registry_register_and_call():
    reg = ToolRegistry()
    reg.register("echo", lambda cmd: {"out": cmd}, schema={"cmd": {"type": str, "required": True}})
    result = reg.call("echo", {"cmd": "hello"})
    assert result["out"] == "hello"

def test_registry_not_found():
    reg = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        reg.call("nonexistent", {})

def test_registry_missing_required_arg():
    reg = ToolRegistry()
    reg.register("noop", lambda x: x, schema={"x": {"type": str, "required": True}})
    with pytest.raises(ToolArgError):
        reg.call("noop", {})

def test_registry_wrong_type():
    reg = ToolRegistry()
    reg.register("noop", lambda x: x, schema={"x": {"type": int, "required": True}})
    with pytest.raises(ToolArgError):
        reg.call("noop", {"x": "not-an-int"})

def test_registry_default_fills():
    reg = ToolRegistry()
    captured = {}
    def fn(x, y=None):
        captured["y"] = y
        return {}
    reg.register("fn", fn, schema={
        "x": {"type": str, "required": True},
        "y": {"type": str, "required": False, "default": "filled"},
    })
    reg.call("fn", {"x": "hi"})
    assert captured["y"] == "filled"

def test_registry_extra_args_passthrough():
    reg = ToolRegistry()
    reg.register("noop", lambda **kw: kw, schema={"x": {"type": str, "required": True}})
    # Should not raise even though 'extra' is not in schema
    reg.call("noop", {"x": "hi", "extra": "ignored"})

def test_registry_list_tools():
    reg = ToolRegistry()
    reg.register("a", lambda: None, schema={})
    reg.register("b", lambda: None, schema={})
    assert "a" in reg.list_tools()
    assert "b" in reg.list_tools()
```

Run gate:
```bash
python scripts/run_pytest_gate.py tests/test_tools.py
```

All tests must pass (exit code 0).

---

## Logging Requirement

Both `tools/terminal.py` and `tools/registry.py` must log to
`logs/luffy-journal.jsonl` on every call using `scripts/append_jsonl.py`.

`terminal.py` log entry (one on call, one on return):
```json
{"timestamp": "...", "tool": "run_command", "cmd": [...], "status": "start"}
{"timestamp": "...", "tool": "run_command", "returncode": 0, "elapsed_ms": 12, "status": "pass"}
```

`registry.py` log entry:
```json
{"timestamp": "...", "tool": "<name>", "args": {...}, "status": "dispatch"}
```

---

## Completion Criteria

- [ ] `tools/__init__.py` exists (empty)
- [ ] `tools/terminal.py` implements `run_command` per spec
- [ ] `tools/registry.py` implements `ToolRegistry`, `ToolNotFoundError`, `ToolArgError`
- [ ] `tests/test_tools.py` exists and all tests pass
- [ ] Both modules log to `logs/luffy-journal.jsonl` on every call
- [ ] Commit message: `feat(step-2): terminal + registry — all tests green`
- [ ] Push to origin/main
