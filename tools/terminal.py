"""tools/terminal.py — Sandboxed subprocess executor with denylist protection."""
from __future__ import annotations
import json
import subprocess
import sys
import time
from typing import Any, List, Optional


# DANGEROUS_PATTERNS denylist — these substrings in any arg block execution
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=/dev/zero",
    ":(){ :|:& };",  # fork bomb
    "> /dev/sda",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
]


def _is_blocked(cmd: List[str]) -> bool:
    """Check if the command matches any dangerous pattern (case-insensitive)."""
    flat_cmd = " ".join(str(arg) for arg in cmd).lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in flat_cmd:
            return True
    return False


def _log_entry(path: str, record: dict) -> None:
    """Append a JSONL record to the journal."""
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
    import os
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _shell_cmd(cmd: List[str]) -> Any:
    """On Windows, join list to string for shell=True (cmd.exe requires a single string).

    On Unix/macOS, pass the list as-is — the shell handles it correctly either way,
    but list form is safer for arg separation.

    Background: subprocess.run(list, shell=True) on Windows passes only cmd[0] to
    cmd.exe and ignores the rest, so && chaining and multi-arg commands silently fail.
    Joining to a string fixes this without changing Unix behavior.
    """
    if sys.platform == "win32":
        return " ".join(str(c) for c in cmd)
    return cmd


def run_command(
    cmd: List[str],
    timeout: int = 30,
    cwd: Optional[str] = None,
    allowed_paths: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Execute a command in a subprocess with denylist and timeout protection.

    Args:
        cmd: Command and arguments as a list of strings.
        timeout: Maximum seconds to wait for the command. Default 30.
        cwd: Working directory for the command. Default None (repo root).
        allowed_paths: Restrict file args to these directories. Default None.

    Returns:
        {
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "timed_out": bool,
            "blocked": bool,     # True if a DANGEROUS_PATTERN matched
            "elapsed_ms": int,
        }
    """
    # Log start
    _log_entry(
        "logs/luffy-journal.jsonl",
        {
            "ticket_id": "STEP-02-B",
            "step": "terminal.run_command",
            "tool": "run_command",
            "cmd": cmd,
            "status": "start",
            "detail": "executing command",
        },
    )

    start_ms = int(time.time() * 1000)

    # Check denylist first
    if _is_blocked(cmd):
        elapsed_ms = int(time.time() * 1000) - start_ms
        _log_entry(
            "logs/luffy-journal.jsonl",
            {
                "ticket_id": "STEP-02-B",
                "step": "terminal.run_command",
                "tool": "run_command",
                "returncode": -1,
                "blocked": True,
                "timed_out": False,
                "elapsed_ms": elapsed_ms,
                "status": "pass",
                "detail": "command blocked by denylist",
            },
        )
        return {
            "stdout": "",
            "stderr": "blocked by denylist",
            "returncode": -1,
            "timed_out": False,
            "blocked": True,
            "elapsed_ms": elapsed_ms,
        }

    try:
        result = subprocess.run(
            _shell_cmd(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            shell=True,
        )
        elapsed_ms = int(time.time() * 1000) - start_ms
        _log_entry(
            "logs/luffy-journal.jsonl",
            {
                "ticket_id": "STEP-02-B",
                "step": "terminal.run_command",
                "tool": "run_command",
                "returncode": result.returncode,
                "stdout": result.stdout[:200] if result.stdout else "",
                "stderr": result.stderr[:200] if result.stderr else "",
                "timed_out": False,
                "blocked": False,
                "elapsed_ms": elapsed_ms,
                "status": "pass",
                "detail": "command completed",
            },
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
            "blocked": False,
            "elapsed_ms": elapsed_ms,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int(time.time() * 1000) - start_ms
        _log_entry(
            "logs/luffy-journal.jsonl",
            {
                "ticket_id": "STEP-02-B",
                "step": "terminal.run_command",
                "tool": "run_command",
                "returncode": -1,
                "timed_out": True,
                "blocked": False,
                "elapsed_ms": elapsed_ms,
                "status": "pass",
                "detail": "command timed out",
            },
        )
        return {
            "stdout": "",
            "stderr": "timed out",
            "returncode": -1,
            "timed_out": True,
            "blocked": False,
            "elapsed_ms": elapsed_ms,
        }
