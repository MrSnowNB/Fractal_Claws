"""tools/registry.py — DEPRECATED: Use src/tools/registry.py instead.

This module is kept as a compatibility shim. The canonical ToolRegistry
lives in src/tools/registry.py and does NOT hardcode ticket_ids in journal
entries. All new code should import from src.tools.registry.

Migration:
    Old: from tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
    New: from src.tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError
"""

import warnings
warnings.warn(
    "tools.registry is deprecated — use src.tools.registry instead",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from canonical location for backward compat
from src.tools.registry import ToolRegistry, ToolNotFoundError, ToolArgError

__all__ = ["ToolRegistry", "ToolNotFoundError", "ToolArgError"]
