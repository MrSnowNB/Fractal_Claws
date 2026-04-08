"""
src/tools/terminal.py — Sandboxed subprocess runner for the Fractal_Claws tool layer.

Provides run_command() used by ToolRegistry and test_tools.py.
Blocks obviously destructive shell patterns before execution.

KNOWN PLATFORM NOTES
--------------------
- Blocklist uses Unix-style patterns (rm -rf /) AND Windows-style patterns (del /f /s /q).
- bash is not available on Windows; tests that invoke bash directly must use
  pytest.mark.skipif(sys.platform == "win32") or use platform-aware commands.
- The pattern 'rm -rf /' appears twice in the original list (duplicate) — kept for
  backward compat with any serialized configs but only matched once at runtime.
"""

import subprocess
import time
from typing import Dict, Any, List, Optional

# Patterns that are blocked regardless of platform.
# KNOWN ISSUE: bash-specific patterns (rm -rf /) do not apply on Windows where
# bash.exe is absent. Windows-equivalent destructive patterns are listed separately.
_BLOCKED_PATTERNS: List[str] = [
    # Unix destructive
    "rm -rf /",
    ":(){ :|:& };:",    # fork bomb (bash)
    "mkfs",
    "dd if=/dev/zero",
    "shutdown",
    "reboot",
    # Windows destructive
    "format c:",
    "del /f /s /q c:\\",
    "rd /s /q c:\\",
    "rmdir /s /q c:\\",
    "del /f /s /q c:/",
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
