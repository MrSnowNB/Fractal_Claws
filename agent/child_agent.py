#!/usr/bin/env python3
"""
child_agent.py — DEPRECATED

This file is kept for reference only.
The active runner is: agent/runner.py

Migration:
    Old: python agent/child_agent.py <ticket_path>
    New: python agent/runner.py  (runner manages its own child execution)
"""
print("[child_agent] DEPRECATED — use: python agent/runner.py")
import sys
sys.exit(0)
