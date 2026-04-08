"""tests/test_runner_dispatch.py — Dispatch and ticket_io tests for STEP-03-B / STEP-05-B."""
import os
import sys
import tempfile
import pytest
from pathlib import Path

from tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
from tools.terminal import run_command
from src.operator_v7 import Ticket, TicketStatus, TicketPriority

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
    """Write minimal ticket YAML. Assert load_ticket returns a Ticket instance with correct id."""
    from agent.runner import load_ticket
    ticket_file = tmp_path / "STEP-TEST-001.yaml"
    ticket_file.write_text(
        "ticket_id: STEP-TEST-001\ntitle: Test ticket\nstatus: open\n"
    )
    ticket = load_ticket(str(ticket_file))
    assert isinstance(ticket, Ticket), f"Expected Ticket, got {type(ticket)}"
    assert ticket.id == "STEP-TEST-001"
    assert ticket.title == "Test ticket"


# ── 11. test_run_command_via_parse_and_run_tools ──────────────────────────────

def test_run_command_via_parse_and_run_tools():
    """Build response with TOOL: run_command PATH: echo hello END. Assert 'hello' in result."""
    cmd = get_windows_cmd() + ["echo", "hello"]
    cmd_str = " ".join(cmd)
    response = f"TOOL: run_command\nPATH: {cmd_str}\nEND"
    results = runner_module.parse_and_run_tools(response, exec_timeout=30)
    _, _, result = results[0]
    assert "hello" in result["stdout"]


# ── 12. test_load_ticket_has_typed_fields ─────────────────────────────────────

def test_load_ticket_has_typed_fields(tmp_path):
    """STEP-05-B: load_ticket populates all Step-5 fields as typed attributes."""
    from agent.runner import load_ticket
    ticket_file = tmp_path / "STEP-FULL-001.yaml"
    ticket_file.write_text(
        "ticket_id: STEP-FULL-001\n"
        "title: Full field test\n"
        "status: open\n"
        "task: Do something\n"
        "depends_on: [STEP-FULL-000]\n"
        "context_files: [output/foo.py]\n"
        "result_path: logs/STEP-FULL-001-result.txt\n"
        "max_tokens: 2048\n"
    )
    ticket = load_ticket(str(ticket_file))
    assert isinstance(ticket, Ticket)
    assert ticket.task == "Do something"
    assert ticket.depends_on == ["STEP-FULL-000"]
    assert ticket.context_files == ["output/foo.py"]
    assert ticket.result_path == "logs/STEP-FULL-001-result.txt"
    assert ticket.max_tokens == 2048


# ── 13. test_consumes_met_happy_path ────────────────────────────────────────────
def test_consumes_met_happy_path(tmp_path):
    """STEP-08-B: _consumes_met returns True when all consumed paths exist."""
    from agent.runner import load_ticket, _consumes_met
    
    # Create a closed ticket with a result file
    os.makedirs("tickets/closed", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Use current working directory for ticket paths (not tmp_path)
    dep_ticket = Path("tickets/closed/STEP-CONSUME-001.yaml")
    dep_ticket.write_text(
        "ticket_id: STEP-CONSUME-001\n"
        "title: Producer ticket\n"
        "status: closed\n"
        "produces: [output/producer.txt]\n"
        "consumes: []\n"
    )
    
    # Create result file with consumed path reference
    result_file = Path("logs/STEP-CONSUME-001-result.txt")
    result_file.write_text("=== tool results ===\noutput/producer.txt\n")
    
    # Create ticket that consumes the produced artifact
    consumer_ticket = Path("tickets/open/STEP-CONSUME-002.yaml")
    consumer_ticket.write_text(
        "ticket_id: STEP-CONSUME-002\n"
        "title: Consumer ticket\n"
        "status: open\n"
        "depends_on: [STEP-CONSUME-001]\n"
        "consumes: [output/producer.txt]\n"
    )
    
    ticket = load_ticket(str(consumer_ticket))
    assert _consumes_met(ticket) is True
    
    # Cleanup
    dep_ticket.unlink(missing_ok=True)
    result_file.unlink(missing_ok=True)
    consumer_ticket.unlink(missing_ok=True)


# ── 14. test_consumes_met_missing_artifact ──────────────────────────────────────
def test_consumes_met_missing_artifact(tmp_path):
    """STEP-08-B: _consumes_met returns False when consumed path doesn't exist."""
    from agent.runner import load_ticket, _consumes_met
    from pathlib import Path
    
    os.makedirs("tickets/open", exist_ok=True)
    
    ticket_file = Path("tickets/open/STEP-CONSUME-003.yaml")
    ticket_file.write_text(
        "ticket_id: STEP-CONSUME-003\n"
        "title: Consumer with missing artifact\n"
        "status: open\n"
        "depends_on: [STEP-CONSUME-001]\n"
        "consumes: [output/nonexistent.txt]\n"
    )
    
    ticket = load_ticket(str(ticket_file))
    assert _consumes_met(ticket) is False
    
    ticket_file.unlink(missing_ok=True)


# ── 15. test_consumes_met_no_consumes ────────────────────────────────────────────
def test_consumes_met_no_consumes(tmp_path):
    """STEP-08-B: _consumes_met returns True when no consumes are specified."""
    from agent.runner import load_ticket, _consumes_met
    from pathlib import Path
    
    os.makedirs("tickets/open", exist_ok=True)
    
    ticket_file = Path("tickets/open/STEP-CONSUME-004.yaml")
    ticket_file.write_text(
        "ticket_id: STEP-CONSUME-004\n"
        "title: Ticket with no consumes\n"
        "status: open\n"
        "consumes: []\n"
    )
    
    ticket = load_ticket(str(ticket_file))
    assert _consumes_met(ticket) is True
    
    ticket_file.unlink(missing_ok=True)


# ── 16. test_consumes_met_multiple_consumes ──────────────────────────────────────
def test_consumes_met_multiple_consumes(tmp_path):
    """STEP-08-B: _consumes_met returns True when all multiple consumed paths exist."""
    from agent.runner import load_ticket, _consumes_met
    from pathlib import Path
    
    os.makedirs("tickets/closed", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Create two closed tickets with result files
    dep1_file = Path("tickets/closed/STEP-CONSUME-10A.yaml")
    dep1_file.write_text(
        "ticket_id: STEP-CONSUME-10A\n"
        "title: First producer\n"
        "status: closed\n"
        "produces: [output/artifact_a.txt]\n"
    )
    Path("logs/STEP-CONSUME-10A-result.txt").write_text("=== tool results ===\noutput/artifact_a.txt\n")
    
    dep2_file = Path("tickets/closed/STEP-CONSUME-10B.yaml")
    dep2_file.write_text(
        "ticket_id: STEP-CONSUME-10B\n"
        "title: Second producer\n"
        "status: closed\n"
        "produces: [output/artifact_b.txt]\n"
    )
    Path("logs/STEP-CONSUME-10B-result.txt").write_text("=== tool results ===\noutput/artifact_b.txt\n")
    
    # Consumer that consumes both artifacts
    consumer_file = Path("tickets/open/STEP-CONSUME-10C.yaml")
    consumer_file.write_text(
        "ticket_id: STEP-CONSUME-10C\n"
        "title: Multi-consumer\n"
        "status: open\n"
        "depends_on: [STEP-CONSUME-10A, STEP-CONSUME-10B]\n"
        "consumes: [output/artifact_a.txt, output/artifact_b.txt]\n"
    )
    
    ticket = load_ticket(str(consumer_file))
    assert _consumes_met(ticket) is True
    
    # Cleanup
    dep1_file.unlink(missing_ok=True)
    dep2_file.unlink(missing_ok=True)
    consumer_file.unlink(missing_ok=True)
    Path("logs/STEP-CONSUME-10A-result.txt").unlink(missing_ok=True)
    Path("logs/STEP-CONSUME-10B-result.txt").unlink(missing_ok=True)


# ── 17. test_detect_deadlock_no_cycle ────────────────────────────────────────────
def test_detect_deadlock_no_cycle(tmp_path):
    """STEP-08-C: _detect_deadlock returns None when no cycle exists."""
    from agent.runner import _detect_deadlock
    
    # Linear chain: A → B → C (no cycle)
    open_tickets = {
        "STEP-CHAIN-A": {"ticket_id": "STEP-CHAIN-A", "depends_on": []},
        "STEP-CHAIN-B": {"ticket_id": "STEP-CHAIN-B", "depends_on": ["STEP-CHAIN-A"]},
        "STEP-CHAIN-C": {"ticket_id": "STEP-CHAIN-C", "depends_on": ["STEP-CHAIN-B"]},
    }
    
    result = _detect_deadlock(open_tickets)
    assert result is None


# ── 18. test_detect_deadlock_simple_cycle ───────────────────────────────────────
def test_detect_deadlock_simple_cycle(tmp_path):
    """STEP-08-C: _detect_deadlock detects a simple A↔B cycle."""
    from agent.runner import _detect_deadlock
    
    # Simple cycle: A → B → A
    open_tickets = {
        "STEP-CYCLE-A": {"ticket_id": "STEP-CYCLE-A", "depends_on": ["STEP-CYCLE-B"]},
        "STEP-CYCLE-B": {"ticket_id": "STEP-CYCLE-B", "depends_on": ["STEP-CYCLE-A"]},
    }
    
    result = _detect_deadlock(open_tickets)
    assert result is not None
    assert "STEP-CYCLE-A" in result
    assert "STEP-CYCLE-B" in result


# ── 19. test_detect_deadlock_three_node_cycle ───────────────────────────────────
def test_detect_deadlock_three_node_cycle(tmp_path):
    """STEP-08-C: _detect_deadlock detects a 3-node cycle A→B→C→A."""
    from agent.runner import _detect_deadlock
    
    # 3-node cycle: A → B → C → A
    open_tickets = {
        "STEP-CYCLE-A": {"ticket_id": "STEP-CYCLE-A", "depends_on": ["STEP-CYCLE-C"]},
        "STEP-CYCLE-B": {"ticket_id": "STEP-CYCLE-B", "depends_on": ["STEP-CYCLE-A"]},
        "STEP-CYCLE-C": {"ticket_id": "STEP-CYCLE-C", "depends_on": ["STEP-CYCLE-B"]},
    }
    
    result = _detect_deadlock(open_tickets)
    assert result is not None
    assert len(result) == 3
    assert "STEP-CYCLE-A" in result
    assert "STEP-CYCLE-B" in result
    assert "STEP-CYCLE-C" in result
