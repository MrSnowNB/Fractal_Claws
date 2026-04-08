"""
src/tools/terminal.py — Sandboxed subprocess runner for the Fractal_Claws tool layer.

Provides run_command() used by ToolRegistry and test_tools.py.
Blocks obviously destructive shell patterns before execution.
"""

import subprocess
import time
from typing import Dict, Any, List, Optional

# Patterns that are blocked regardless of platform.
_BLOCKED_PATTERNS: List[str] = [
    "rm -rf /",
    "rm -rf /",
    ":(){ :|:& };:",   # fork bomb
    "mkfs",
    "dd if=/dev/zero",
    "shutdown",
    "reboot",
    "format c:",
]


def _is_blocked(cmd: List[str]) -> bool:
    """Return True if cmd matches any blocked pattern."""
    flat = " ".join(str(c) for c in cmd).lower()
    return any(p.lower() in flat for p in _BLOCKED_PATTERNS)


def run_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    timeout: int = 30,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run a subprocess command and return a structured result dict.

    Returns:
        {
            "returncode": int,   # -1 on timeout or block
            "stdout":     str,
            "stderr":     str,
            "elapsed_ms": int,
            "timed_out":  bool,
            "blocked":    bool,
        }
    """
    if _is_blocked(cmd):
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "BLOCKED: command matches blocklist",
            "elapsed_ms": 0,
            "timed_out": False,
            "blocked": True,
        }

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env=env,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_ms": elapsed,
            "timed_out": False,
            "blocked": False,
        }
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"TIMEOUT: command exceeded {timeout}s",
            "elapsed_ms": elapsed,
            "timed_out": True,
            "blocked": False,
        }
