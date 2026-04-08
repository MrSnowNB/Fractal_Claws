"""tests/test_tools.py — Validation gate for terminal + registry modules.

KNOWN PLATFORM ISSUES
----------------------
test_run_command_blocked_unix:
    Uses 'bash -c "rm -rf /"' which requires bash. bash is NOT available on
    Windows by default. This test is skipped on win32 and replaced by
    test_run_command_blocked_windows which uses cmd.exe syntax.
    Resolution: both tests verify the blocklist fires; together they give
    full cross-platform coverage.
"""
import sys
import pytest
from pathlib import Path

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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "KNOWN ISSUE: bash is not available on Windows. "
        "Blocklist coverage for Windows is provided by test_run_command_blocked_windows. "
        "Resolution: install Git Bash or WSL to enable this test on Windows."
    ),
)
def test_run_command_blocked_unix():
    """Unix: blocklist intercepts 'bash -c rm -rf /' before subprocess is spawned."""
    r = run_command(["bash", "-c", "rm -rf /"])
    assert r["blocked"] is True
    assert r["returncode"] == -1


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-specific blocklist test. Unix equivalent: test_run_command_blocked_unix.",
)
def test_run_command_blocked_windows():
    """Windows: blocklist intercepts 'del /f /s /q c:\\' before subprocess is spawned."""
    r = run_command(["cmd", "/c", "del /f /s /q c:\\"])
    assert r["blocked"] is True
    assert r["returncode"] == -1


def test_run_command_elapsed_ms():
    r = run_command(["echo", "hi"])
    assert isinstance(r["elapsed_ms"], int)
    assert r["elapsed_ms"] >= 0


def test_run_command_cwd(tmp_path):
    import platform
    if platform.system() == "Windows":
        r = run_command(["cmd", "/c", "echo %CD%"], cwd=str(tmp_path))
    else:
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
    reg.call("noop", {"x": "hi", "extra": "ignored"})


def test_registry_list_tools():
    reg = ToolRegistry()
    reg.register("a", lambda: None, schema={})
    reg.register("b", lambda: None, schema={})
    assert "a" in reg.list_tools()
    assert "b" in reg.list_tools()
