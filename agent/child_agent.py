#!/usr/bin/env python3
"""
child_agent.py — Fractal Claws POC child agent.

Usage:
    python agent/child_agent.py <ticket_path>

Receives a ticket YAML, reads context files, calls the 4B model once,
writes the result, updates the ticket, and exits.

Hardware: HP ZBook (single node)
Endpoint: Lemonade at http://localhost:8000/api/v1
Model: Qwen3.5-4B-GGUF
"""
import sys
import os
import time
import yaml
from openai import OpenAI

MODEL    = "Qwen3.5-4B-GGUF"
ENDPOINT = "http://localhost:8000/api/v1"
API_KEY  = "x"

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


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
    parts = []
    for cf in ticket.get("context_files", []):
        parts.append(f"--- {cf} ---\n{read_file(cf)}")
    return "\n\n".join(parts)


def build_user_prompt(ticket: dict, context: str) -> str:
    prompt = f"{ticket['task']}"
    if context.strip():
        prompt += f"\n\nContext:\n{context}"
    return prompt


def main():
    if len(sys.argv) < 2:
        print("Usage: python agent/child_agent.py <ticket_path>")
        sys.exit(1)

    ticket_path = sys.argv[1]
    if not os.path.exists(ticket_path):
        print(f"ERROR: ticket not found: {ticket_path}")
        sys.exit(1)

    # 1. Load ticket
    ticket = load_ticket(ticket_path)
    ticket_id = ticket.get("ticket_id", os.path.basename(ticket_path))
    print(f"[child] loaded ticket: {ticket_id}")

    # 2. Setup closed destination
    dest_dir = "tickets/closed"
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(ticket_path))
    print(f"[child] dest: {dest}")

    # 3. Read context
    context = build_context(ticket)

    # 4. Call model with thinking disabled
    system_prompt = "You are a helpful assistant. Reply concisely, no markdown."
    user_prompt   = build_user_prompt(ticket, context)

    print(f"[child] calling model: {MODEL}")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=ticket.get("max_tokens", 512),
        temperature=0.2,
        timeout=ticket.get("timeout_seconds", 90),
        extra_body={"enable_thinking": False},
    )

    raw   = response.choices[0].message.content.strip()
    used  = response.usage.total_tokens if response.usage else 0
    why   = response.choices[0].finish_reason
    print(f"[child] responded ({used} tokens, finish={why})")
    print(f"[child] repr: {repr(raw[:200])}")

    # 5. Write result
    result_path = ticket.get("result_path", "")
    out_dir = os.path.dirname(result_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    content = raw if raw else "NO RESPONSE"
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[child] wrote: {result_path}")

    # 6. Move + close ticket
    os.replace(ticket_path, dest)
    ticket["status"]     = "closed"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_ticket(dest, ticket)
    print(f"[child] closed: {dest}")
    print(f"[child] done")


if __name__ == "__main__":
    main()
