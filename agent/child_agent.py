#!/usr/bin/env python3
"""
child_agent.py — Fractal Claws POC child agent.

Usage:
    python agent/child_agent.py <ticket_path>

Receives a ticket YAML, reads context files, calls the 4B model once,
parses a write_file command from the response, writes the result,
updates the ticket, and exits.

Tools available to child: read_file, write_file ONLY.
No browser. No shell. No network. No code interpreter.
"""
import sys
import os
import time
import subprocess
import re
import yaml
from openai import OpenAI

MODEL = "Qwen3.5-4B-GGUF"
ENDPOINT = "http://localhost:11434/v1"
API_KEY = "ollama"  # openai-compat placeholder

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


# ───────────────────────────────────────────────────────────────────────────
def load_ticket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_ticket(path: str, ticket: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


def move_ticket(src: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(src)
    dest = os.path.join(dest_dir, filename)
    os.replace(src, dest)
    return dest


def run_read_file(filepath: str) -> str:
    """Run tools/read_file.py and return stdout."""
    result = subprocess.run(
        [sys.executable, "tools/read_file.py", filepath],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        return f"ERROR reading {filepath}: {result.stdout.strip()}"
    return result.stdout


def run_write_file(filepath: str, content: str) -> str:
    """Run tools/write_file.py with content via stdin."""
    result = subprocess.run(
        [sys.executable, "tools/write_file.py", filepath, "--stdin"],
        input=content, capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def build_system_prompt(ticket: dict) -> str:
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

    # ─ 2. Move to in_progress
    in_progress_path = move_ticket(ticket_path, "tickets/in_progress")
    ticket["status"] = "in_progress"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_ticket(in_progress_path, ticket)
    print(f"[child] status: in_progress")

    attempt_start = time.time()
    outcome = "failed"
    tokens_used = 0

    try:
        # ─ 3. Read context files
        context_parts = []
        for cf in ticket.get("context_files", []):
            print(f"[child] reading context: {cf}")
            contents = run_read_file(cf)
            context_parts.append(f"--- {cf} ---\n{contents}")
        context = "\n\n".join(context_parts)

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
            raise ValueError("no write_file command in response")

        write_path, write_content = parsed

        # Enforce: child may only write to result_path
        if write_path != result_path:
            print(f"[child] WARNING: model tried to write to {write_path}, redirecting to {result_path}")
            write_path = result_path

        # ─ 6. Execute write
        print(f"[child] writing result to: {write_path}")
        write_result = run_write_file(write_path, write_content)

        if write_result != "OK":
            raise ValueError(f"write_file failed: {write_result}")

        print(f"[child] write OK")
        outcome = "success"

    except Exception as e:
        print(f"[child] EXCEPTION: {e}")
        ticket["decrement"] = ticket.get("decrement", 3) - 1
        if ticket["decrement"] <= 0:
            ticket["status"] = "escalated"
        save_ticket(in_progress_path, ticket)
        sys.exit(1)

    # ─ 7. Close ticket
    elapsed = round(time.time() - attempt_start, 2)
    attempt_record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "attempt_num": len(ticket.get("attempts", [])) + 1,
        "outcome": outcome,
        "tokens_used": tokens_used,
        "elapsed_seconds": elapsed,
    }
    if "attempts" not in ticket or ticket["attempts"] is None:
        ticket["attempts"] = []
    ticket["attempts"].append(attempt_record)
    ticket["status"] = "closed"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    closed_path = move_ticket(in_progress_path, "tickets/closed")
    save_ticket(closed_path, ticket)
    print(f"[child] ticket closed: {closed_path}")
    print(f"[child] done in {elapsed}s")
    sys.exit(0)


if __name__ == "__main__":
    main()
