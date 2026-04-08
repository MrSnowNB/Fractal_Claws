"""
tests/conftest.py — test-level path setup.

The root conftest.py already puts src/ on sys.path.
This file is kept minimal to avoid re-adding the path.
"""
import sys
from pathlib import Path

# Ensure src/ is on path (idempotent — root conftest handles it first).
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
