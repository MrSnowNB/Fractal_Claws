"""
Root conftest.py — puts src/ on sys.path so tests can import:
  from tools.registry import ...
  from tools.terminal import ...
  from operator_v7 import ...
  from ticket_io import ...
without needing 'src.' prefix in every test file.
"""
import sys
from pathlib import Path

# Insert src/ at position 0 so it takes priority over installed packages.
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
