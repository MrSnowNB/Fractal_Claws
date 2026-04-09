"""tools/terminal.py — DEPRECATED: Use src/tools/terminal.py instead.

This module is kept as a compatibility shim. The canonical run_command()
lives in src/tools/terminal.py and does NOT hardcode ticket_ids or
write to the journal on every call. All new code should import from
src.tools.terminal.

Migration:
    Old: from tools.terminal import run_command
    New: from src.tools.terminal import run_command
"""

import warnings
warnings.warn(
    "tools.terminal is deprecated — use src.tools.terminal instead",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from canonical location for backward compat
from src.tools.terminal import run_command

__all__ = ["run_command"]
