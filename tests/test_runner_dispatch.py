"""tests/test_runner_dispatch.py — Dispatch and ticket_io tests for STEP-03-B."""
import os
import sys
import tempfile
import pytest

from tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
from tools.terminal import run_command

# Import from agent.runner (the module-level REGISTRY is already instantiated)
import agent.runner as runner_module


# ── helper ─────────────────────────────────────────────────────────────────────

def get_windows_cmd():
    """Return correct cmd list for Windows vs Unix."""
    if sys.platform.startswith("win"):
        return ["cmd", "/c"]
    return ["sh", "-c"]


# ── 1. test_registry_registered_tools ──────────────────────────────────────────

def test_registry_registered_tools():
    """Assert all five tool names are registered in REGISTRY."""
    tools = runner_module.REGISTRY.list_tools()
    assert "read_file" in tools
    assert "write_file" in tools
    assert "list_dir" in tools
    assert "exec_python" in tools
    assert "run_command" in tools


# ── 2. test_dispatch_read_file ────────────────────────────────────────────────

def test_dispatch_read_file(tmp_path):
    """Call REGISTRY.call("read_file", {"path": tmp_path}). Assert content matches."""
    test_file = tmp_path / "read_test.txt"
    test_file.write_text("test_content_123")
    result = runner_module.REGISTRY.call("read_file", {"path": str(test_file)})
    assert "test_content_123" in result


# ── 3. test_dispatch_write_file ───────────────────────────────────────────────

def test_dispatch_write_file(tmp_path):
    """Call REGISTRY.call("write_file", {"path": tmp_path, "content": "hello"})."""
    test_file = tmp_path / "write_test.txt"
    result = runner_module.REGISTRY.call("write_file", {"path": str(test_file), "content": "hello"})
    assert "OK:" in result
    assert test_file.read_text() == "hello"


# ── 4. test_dispatch_list_dir ─────────────────────────────────────────────────

def test_dispatch_list_dir(tmp_path):
    """Create temp dir with one file. Assert filename appears in result."""
    test_dir = tmp_path / "list_test_dir"
    test_dir.mkdir()
    (test_dir / "file_in_dir.txt").write_text("content")
    result = runner_module.REGISTRY.call("list_dir", {"path": str(test_dir)})
    assert "file_in_dir.txt" in result


# ── 5. test_dispatch_exec_python ──────────────────────────────────────────────

def test_dispatch_exec_python(tmp_path):
    """Write trivial Python script to output/test_dispatch.py. Assert 'dispatch_ok' in result."""
    os.makedirs("output", exist_ok=True)
    script = "output/test_dispatch.py"
    (tmp_path / script).parent.mkdir(exist_ok=True)
    (tmp_path / script).write_text('print("dispatch_ok")')
    # Copy to output dir where exec_python expects it
    os.makedirs("output", exist_ok=True)
    with open("output/test_dispatch.py", "w") as f:
        f.write('print("dispatch_ok")')
    result = runner_module.REGISTRY.call("exec_python", {"path": "output/test_dispatch.py"})
    assert "dispatch_ok" in result


# ── 6. test_dispatch_run_command ──────────────────────────────────────────────

def test_dispatch_run_command():
    """Call REGISTRY.call("run_command", {"cmd": [...]}). Assert 'registry_ok' in result."""
    cmd = get_windows_cmd() + ["echo", "registry_ok"]
    result = runner_module.REGISTRY.call("run_command", {"cmd": cmd})
    assert "registry_ok" in result["stdout"]


# ── 7. test_dispatch_unknown_tool ─────────────────────────────────────────────

def test_dispatch_unknown_tool():
    """Call REGISTRY.call("nonexistent_tool", ...). Expect ToolNotFoundError."""
    with pytest.raises(ToolNotFoundError):
        runner_module.REGISTRY.call("nonexistent_tool", {"path": "/"})


# ── 8. test_parse_and_run_tools_write_then_exec ───────────────────────────────

def test_parse_and_run_tools_write_then_exec(tmp_path):
    """Build synthetic response with write_file → exec_python. Assert 42 in result."""
    os.makedirs("output", exist_ok=True)
    response = (
        "TOOL: write_file\n"
        "PATH: output/dispatch_test.py\n"
        "CONTENT:\n"
        "print(42)\n"
        "END\n"
        "TOOL: exec_python\n"
        "PATH: output/dispatch_test.py\n"
        "END"
    )
    results = runner_module.parse_and_run_tools(response, exec_timeout=30)
    assert len(results) == 2
    _, _, exec_result = results[1]
    assert "42" in exec_result


# ── 9. test_parse_and_run_tools_unknown_tool_returns_error ───────────────────

def test_parse_and_run_tools_unknown_tool_returns_error():
    """Build response with TOOL: bogus_tool PATH: /tmp/x END. Assert 'ERROR:' in result."""
    response = "TOOL: bogus_tool\nPATH: /tmp/x\nEND"
    results = runner_module.parse_and_run_tools(response, exec_timeout=30)
    _, _, result = results[0]
    assert "ERROR:" in result


# ── 10. test_typed_ticket_load ────────────────────────────────────────────────

def test_typed_ticket_load(tmp_path):
    """Write minimal ticket YAML. Import load_ticket. Assert ticket_id matches."""
    from agent.runner import load_ticket
    ticket_file = tmp_path / "test_ticket.yaml"
    ticket_file.write_text(
        "ticket_id: STEP-TEST-001\ntitle: Test ticket\nstatus: open\n"
    )
    ticket = load_ticket(str(ticket_file))
    assert ticket["ticket_id"] == "STEP-TEST-001"


# ── 11. test_run_command_via_parse_and_run_tools ──────────────────────────────

def test_run_command_via_parse_and_run_tools():
    """Build response with TOOL: run_command PATH: echo hello END. Assert 'hello' in result."""
    cmd = get_windows_cmd() + ["echo", "hello"]
    cmd_str = " ".join(cmd)
    response = f"TOOL: run_command\nPATH: {cmd_str}\nEND"
    results = runner_module.parse_and_run_tools(response, exec_timeout=30)
    _, _, result = results[0]
    assert "hello" in result["stdout"]