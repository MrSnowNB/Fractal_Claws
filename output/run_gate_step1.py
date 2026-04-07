"""
run_gate_step1.py — Step 1 Validation Gate Runner

Executed by the coding agent in the harness to validate Step 1.
Passes if all tests in tests/test_ticket_io.py are green.
Exits with non-zero return code on any failure so the runner marks the ticket escalated.

Vendor-agnostic: no model, no endpoint, no network.
Requires: python 3.10+, pyyaml, pytest
"""
import subprocess
import sys
import os

# Ensure we run from repo root regardless of cwd
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(repo_root)

result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "tests/test_ticket_io.py",
        "-v",
        "--tb=short",
        "--no-header",
        "-q",
    ],
    capture_output=True,
    text=True,
)

print(result.stdout)
if result.stderr.strip():
    print("STDERR:", result.stderr)

if result.returncode == 0:
    print("\n[GATE STEP-1] PASS — all ticket_io tests green. Step 2 is unlocked.")
else:
    print("\n[GATE STEP-1] FAIL — fix failures above before proceeding to Step 2.")

sys.exit(result.returncode)
