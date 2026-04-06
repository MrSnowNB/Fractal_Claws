#!/usr/bin/env python3
"""
write_file.py — Child agent write tool.

Usage:
    python tools/write_file.py <filepath> "<content>"

Writes content to filepath (creates or overwrites).
Prints OK on success, ERROR:<reason> on failure.
Exits 0 on success, 1 on error.

Note: content is taken as argv[2]. For multi-line content,
the caller should pass content via stdin instead:
    echo "content" | python tools/write_file.py <filepath> --stdin
"""
import sys
import os


def main():
    if len(sys.argv) < 2:
        print("ERROR: no filepath provided")
        print("Usage: python tools/write_file.py <filepath> \"<content>\"")
        sys.exit(1)

    filepath = sys.argv[1]

    # Support --stdin flag for multi-line content
    if len(sys.argv) >= 3 and sys.argv[2] == "--stdin":
        content = sys.stdin.read()
    elif len(sys.argv) >= 3:
        content = sys.argv[2]
    else:
        print("ERROR: no content provided")
        print("Usage: python tools/write_file.py <filepath> \"<content>\"")
        sys.exit(1)

    # Ensure parent directory exists
    parent = os.path.dirname(filepath)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as e:
            print(f"ERROR: could not create directory {parent}: {e}")
            sys.exit(1)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("OK")
        sys.exit(0)
    except PermissionError:
        print(f"ERROR: permission denied: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
