#!/usr/bin/env python3
"""
child_agent.py — Fractal Claws POC child agent.

Usage:
    python agent/child_agent.py <ticket_path>

Receives a ticket YAML, reads context files, calls the 4B model once,
writes the result, updates the ticket, and exits.

Tools available to child: read_file, write_file.
No browser. No shell. No network. No code interpreter.
"""
import sys
import os
import re
import time
import yaml
from openai import OpenAI

MODEL = "Qwen3.5-4B-GGUF"
ENDPOINT = "http://localhost:8000/api/v1"
API_KEY = "x"

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


# ───────────────────────────────────────────────────────────────────────────
def load_ticket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    # merge frontmatter + body if two docs, otherwise return single doc
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0]


def save_ticket(path: str, ticket: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


def move_ticket(src: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(src)
    dest = os.path.join(dest_dir, filename)
    os.replace(src, dest)
    return dest


def read_file(filepath: str) -> str:
    """Read a file and return its contents."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_context(ticket: dict) -> str:
    """Build context from context_files."""
    context_parts = []
    for cf in ticket.get("context_files", []):
        content = read_file(cf)
        context_parts.append(f"--- {cf} ---\n{content}")
    return "\n\n".join(context_parts)


def build_system_prompt(ticket: dict) -> str:
    """Build system prompt with tool descriptions."""
    tool_block = ""
    for t in ticket.get("allowed_tools", []):
        tool_block += (
            f"\nTool: {t['name']}\n"
            f"  Usage: {t['usage']}\n"
            f"  Description: {t['description']}\n"
        )

    return (
        "You are a coding assistant. You have exactly two tools:\n"
        f"{tool_block}\n"
        "RULES:\n"
        "- You may NOT use any tool not listed above.\n"
        "- You must call write_file exactly ONCE as your final action.\n"
        "- Do NOT narrate. Do NOT explain. Do NOT use markdown.\n"
        "- Your entire response must be a single write_file command on one line:\n"
        f'  write_file {ticket["result_path"]} "<your answer here>"\n'
        "- If your answer contains newlines, use \\n in the string.\n"
        "- Do not include any text before or after the write_file command.\n"
    )


def build_user_prompt(ticket: dict, context: str) -> str:
    """Build user prompt with task description."""
    prompt = f"Task: {ticket['task']}\n"
    if context.strip():
        prompt += f"\nContext:\n{context}\n"
    prompt += f"\nWrite your result to: {ticket['result_path']}"
    return prompt


def parse_write_command(response: str, result_path: str) -> tuple[str, str] | None:
    """
    Parse: write_file <path> "<content>"
    Returns (path, content) or None if not found.
    """
    # Match: write_file <path> "content" or write_file <path> 'content'
    pattern = r'write_file\s+(\S+)\s+["\'](.+)["\']'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        path = match.group(1)
        content = match.group(2).replace("\\n", "\n")
        return path, content

    # Fallback: write_file <path> <rest of line unquoted>
    pattern2 = r'write_file\s+(\S+)\s+(.+)'
    match2 = re.search(pattern2, response)
    if match2:
        path = match2.group(1)
        content = match2.group(2).replace("\\n", "\n")
        return path, content

    return None


# ───────────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("ERROR: no ticket path provided")
        print("Usage: python agent/child_agent.py <ticket_path>")
        sys.exit(1)

    ticket_path = sys.argv[1]

    if not os.path.exists(ticket_path):
        print(f"ERROR: ticket not found: {ticket_path}")
        sys.exit(1)

    # ─ 1. Load ticket
    ticket = load_ticket(ticket_path)
    ticket_id = ticket.get("ticket_id", os.path.basename(ticket_path))
    print(f"[child] loaded ticket: {ticket_id}")

    # ─ 2. Move to closed (skip in_progress for simplicity)
    dest_dir = "tickets/closed"
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(ticket_path)
    dest = os.path.join(dest_dir, filename)
    os.replace(ticket_path, dest)
    print(f"[child] ticket copied to: {dest}")

    # ─ 3. Read context files
    context = build_context(ticket)

    # ─ 4. Build prompt and call model
    system_prompt = build_system_prompt(ticket)
    user_prompt = build_user_prompt(ticket, context)

    print(f"[child] calling model: {MODEL}")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=ticket.get("max_tokens", 512),
        temperature=0.2,
        timeout=ticket.get("timeout_seconds", 90),
    )

    raw_response = response.choices[0].message.content.strip()
    tokens_used = response.usage.total_tokens if response.usage else 0
    print(f"[child] model responded ({tokens_used} tokens)")

    # ─ 5. Parse write_file command from response
    result_path = ticket.get("result_path", "")
    parsed = parse_write_command(raw_response, result_path)

    if not parsed:
        print(f"[child] ERROR: model did not produce a write_file command")
        print(f"[child] raw response: {raw_response[:200]}")
        sys.exit(1)

    write_path, write_content = parsed

    # ─ 6. Execute write
    print(f"[child] writing result to: {write_path}")
    with open(write_path, "w", encoding="utf-8") as f:
        f.write(write_content)
    print(f"[child] write OK")

    # ─ 7. Update ticket
    ticket["status"] = "closed"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    # ─ 8. Save updated ticket
    save_ticket(dest, ticket)
    print(f"[child] ticket closed: {dest}")
    print(f"[child] done")


if __name__ == "__main__":
    main()