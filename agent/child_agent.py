#!/usr/bin/env python3
"""
child_agent.py — Fractal Claws child agent.

Usage:
    python agent/child_agent.py <ticket_path>

Tools available to the model:
  read_file   <path>
  write_file  <path>
  <content>
  END
  exec_python <path>

The model emits tool calls in its response. This agent parses and
executes them in sequence, then writes a summary to result_path.

Safety: exec_python is restricted to the output/ directory.
"""
import sys
import os
import re
import time
import subprocess
import yaml
from openai import OpenAI

MODEL    = "Qwen3.5-4B-GGUF"
ENDPOINT = "http://localhost:8000/api/v1"
API_KEY  = "x"
EXEC_DIR = "output"  # exec_python is sandboxed to this directory

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


# ────────────────────────────── ticket helpers
def load_ticket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0]


def save_ticket(path: str, ticket: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


# ────────────────────────────── tools
def tool_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"ERROR: file not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tool_write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"OK: wrote {len(content)} bytes to {path}"


def tool_exec_python(path: str, timeout: int = 30) -> str:
    # Safety: only allow execution from output/ directory
    abs_path   = os.path.abspath(path)
    abs_exec   = os.path.abspath(EXEC_DIR)
    if not abs_path.startswith(abs_exec):
        return f"ERROR: exec_python blocked — path must be inside {EXEC_DIR}/ (got {path})"
    if not os.path.exists(abs_path):
        return f"ERROR: file not found: {path}"
    try:
        result = subprocess.run(
            [sys.executable, abs_path],
            capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        lines = []
        if out:
            lines.append(f"STDOUT:\n{out}")
        if err:
            lines.append(f"STDERR:\n{err}")
        lines.append(f"returncode: {result.returncode}")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return f"ERROR: exec_python timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: exec_python failed: {e}"


# ────────────────────────────── tool call parser
BLOCK_RE = re.compile(
    r'TOOL:\s*(\S+)\s*\nPATH:\s*(\S+)\s*\n(?:CONTENT:\n([\s\S]*?)\nEND|END)',
    re.MULTILINE
)

def parse_and_run_tools(response_text: str, exec_timeout: int = 30) -> list:
    """
    Parse tool calls from model response and execute them.
    Returns list of (tool, path, result) tuples.
    """
    results = []
    for match in BLOCK_RE.finditer(response_text):
        tool    = match.group(1).strip()
        path    = match.group(2).strip()
        content = match.group(3)  # None for read_file / exec_python

        print(f"[child] tool: {tool} path: {path}")

        if tool == "read_file":
            result = tool_read_file(path)
        elif tool == "write_file":
            result = tool_write_file(path, content or "")
        elif tool == "exec_python":
            result = tool_exec_python(path, timeout=exec_timeout)
        else:
            result = f"ERROR: unknown tool: {tool}"

        print(f"[child] result: {result[:120]}")
        results.append((tool, path, result))

    return results


# ────────────────────────────── prompt builders
TOOL_SYNTAX = """You have these tools. Use them by emitting blocks exactly as shown.

read_file:
  TOOL: read_file
  PATH: <path>
  END

write_file:
  TOOL: write_file
  PATH: <path>
  CONTENT:
  <file content here>
  END

exec_python:
  TOOL: exec_python
  PATH: <path>
  END

Rules:
- exec_python may only reference files inside output/
- Emit tool blocks only. No prose before or after.
- After all tools, write one final line: DONE
"""

def build_context(ticket: dict) -> str:
    parts = []
    for cf in ticket.get("context_files", []):
        parts.append(f"--- {cf} ---\n{tool_read_file(cf)}")
    return "\n\n".join(parts)


def build_user_prompt(ticket: dict, context: str) -> str:
    prompt = TOOL_SYNTAX
    prompt += f"\nTask:\n{ticket['task']}"
    if context.strip():
        prompt += f"\n\nContext:\n{context}"
    return prompt


# ────────────────────────────── main
def main():
    if len(sys.argv) < 2:
        print("Usage: python agent/child_agent.py <ticket_path>")
        sys.exit(1)

    ticket_path = sys.argv[1]
    if not os.path.exists(ticket_path):
        print(f"ERROR: ticket not found: {ticket_path}")
        sys.exit(1)

    # 1. Load
    ticket    = load_ticket(ticket_path)
    ticket_id = ticket.get("ticket_id", os.path.basename(ticket_path))
    print(f"[child] loaded ticket: {ticket_id}")

    dest_dir = "tickets/closed"
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(ticket_path))

    # 2. Build prompt
    context     = build_context(ticket)
    user_prompt = build_user_prompt(ticket, context)
    system_prompt = "You are a code-executing agent. Follow the tool syntax exactly. No markdown fences."

    # 3. Call model
    print(f"[child] calling model: {MODEL}")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=ticket.get("max_tokens", 1024),
        temperature=0.1,
        timeout=ticket.get("timeout_seconds", 120),
    )

    raw  = response.choices[0].message.content or ""
    used = response.usage.total_tokens if response.usage else 0
    why  = response.choices[0].finish_reason
    print(f"[child] responded ({used} tokens, finish={why})")
    print(f"[child] raw:\n{raw[:600]}")

    # 4. Parse and run tools
    os.makedirs(EXEC_DIR, exist_ok=True)
    tool_results = parse_and_run_tools(raw, exec_timeout=ticket.get("timeout_seconds", 30))

    # 5. Write result summary
    result_path = ticket.get("result_path", "logs/result.txt")
    os.makedirs(os.path.dirname(result_path) if os.path.dirname(result_path) else ".", exist_ok=True)

    summary_lines = [f"ticket: {ticket_id}", f"finish: {why}", f"tokens: {used}", ""]
    if tool_results:
        for tool, path, result in tool_results:
            summary_lines.append(f"[{tool}] {path}")
            summary_lines.append(result)
            summary_lines.append("")
    else:
        summary_lines.append("no tool calls detected")
        summary_lines.append("")
        summary_lines.append("raw response:")
        summary_lines.append(raw)

    summary = "\n".join(summary_lines)
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"[child] wrote: {result_path}")

    # 6. Close ticket
    os.replace(ticket_path, dest)
    ticket["status"]     = "closed"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_ticket(dest, ticket)
    print(f"[child] closed: {dest}")
    print(f"[child] done")


if __name__ == "__main__":
    main()
