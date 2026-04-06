#!/usr/bin/env python3
"""
read_file.py — Child agent read tool.

Usage:
    python tools/read_file.py <filepath>

Returns file contents to stdout.
Exits 0 on success, 1 on error (error message goes to stdout prefixed ERROR:).
"""
import sys
import os


def main():
    if len(sys.argv) < 2:
        print("ERROR: no filepath provided")
        print("Usage: python tools/read_file.py <filepath>")
        sys.exit(1)

    filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"ERROR: file not found: {filepath}")
        sys.exit(1)

    if not os.path.isfile(filepath):
        print(f"ERROR: path is not a file: {filepath}")
        sys.exit(1)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            contents = f.read()
        print(contents)
        sys.exit(0)
    except PermissionError:
        print(f"ERROR: permission denied: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
