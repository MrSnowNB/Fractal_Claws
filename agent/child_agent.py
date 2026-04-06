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
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0]


def save_ticket(path: str, ticket: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


def read_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_context(ticket: dict) -> str:
    context_parts = []
    for cf in ticket.get("context_files", []):
        content = read_file(cf)
        context_parts.append(f"--- {cf} ---\n{content}")
    return "\n\n".join(context_parts)


def build_user_prompt(ticket: dict, context: str) -> str:
    prompt = f"Task: {ticket['task']}\n"
    if context.strip():
        prompt += f"\nContext:\n{context}\n"
    # /no_think suppresses Qwen3 thinking block so tokens go to the answer
    prompt += "\n/no_think"
    return prompt


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

    # ─ 2. Setup destination
    dest_dir = "tickets/closed"
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(ticket_path)
    dest = os.path.join(dest_dir, filename)
    print(f"[child] ticket will be saved to: {dest}")

    # ─ 3. Read context files
    context = build_context(ticket)

    # ─ 4. Build prompt and call model
    system_prompt = "You are a helpful assistant. Do not use markdown. Reply concisely."
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
    finish_reason = response.choices[0].finish_reason
    print(f"[child] model responded ({tokens_used} tokens, finish={finish_reason})")
    print(f"[child] raw_response repr: {repr(raw_response[:200])}")

    # ─ 5. Write response to result_path
    result_path = ticket.get("result_path", "")
    write_content = raw_response if raw_response else "NO RESPONSE"

    os.makedirs(os.path.dirname(result_path) if os.path.dirname(result_path) else ".", exist_ok=True)
    print(f"[child] writing result to: {result_path}")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(write_content)
    print(f"[child] write OK")

    # ─ 6. Move ticket to closed
    os.replace(ticket_path, dest)
    print(f"[child] ticket moved to: {dest}")

    # ─ 7. Update and save ticket
    ticket["status"] = "closed"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_ticket(dest, ticket)
    print(f"[child] ticket closed: {dest}")
    print(f"[child] done")


if __name__ == "__main__":
    main()
