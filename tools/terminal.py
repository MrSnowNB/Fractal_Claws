#!/usr/bin/env python3
"""
terminal.py — Child agent shell command execution tool.

Usage:
    python tools/terminal.py <command>

Runs a shell command and returns stdout/stderr/returncode as JSON to stdout.
Exits 0 on success, 1 on error (error message goes to stdout prefixed ERROR:).

Logging:
    All executions are logged to logs/luffy-journal.jsonl per Luffy Law.
"""
import sys
import os
import json
import subprocess
import time


def run_command(cmd: str) -> dict:
    """Run a shell command and return result dict with stdout, stderr, returncode."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }


def append_jsonl(path: str, record: dict) -> None:
    """Append a dict as a JSONL line to an audit log file."""
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main():
    if len(sys.argv) < 2:
        print("ERROR: no command provided")
        print("Usage: python tools/terminal.py <command>")
        sys.exit(1)

    cmd = sys.argv[1]

    try:
        result = run_command(cmd)
        output = json.dumps(result)
        print(output)

        # Log per Luffy Law: all activity to logs/luffy-journal.jsonl
        log_record = {
            "event": "terminal_run_command",
            "command": cmd,
            "returncode": result["returncode"],
            "stdout_length": len(result["stdout"]),
            "stderr_length": len(result["stderr"])
        }
        append_jsonl("logs/luffy-journal.jsonl", log_record)

        sys.exit(0)
    except PermissionError:
        print(f"ERROR: permission denied executing command: {cmd}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()