#!/usr/bin/env python3
"""
daemon_4b.py — Fractal Claws 4B Daemon

Plants a persistent Qwen3.5-4B-GGUF session that:
  - Listens for prompt files dropped into experiments/daemon/inbox/
  - Responds to each prompt, writing results to experiments/daemon/outbox/
  - Logs every exchange to experiments/daemon/logs/session.jsonl
  - Exposes a /status endpoint (localhost:7700) for health checks
  - Shuts down cleanly when experiments/daemon/SHUTDOWN is created
  - Writes a final summary to experiments/daemon/logs/final_summary.json on exit

Usage:
    python experiments/daemon/daemon_4b.py

Shutdown (from Cline or any process):
    Write any file to experiments/daemon/SHUTDOWN
    — daemon detects it within the poll interval and exits gracefully.

All paths are relative to repo root. Run from repo root.
"""

import os
import sys
import json
import time
import threading
import hashlib
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI

# ── config ────────────────────────────────────────────────────────────────────
MODEL         = "Qwen3.5-4B-GGUF"
ENDPOINT      = "http://localhost:8000/api/v1"
API_KEY       = "x"
POLL_S        = 1.5          # inbox poll interval (seconds)
STATUS_PORT   = 7700         # /status HTTP port
MAX_TOKENS    = 512
TEMPERATURE   = 0.2
CALL_TIMEOUT  = 60

# ── paths (relative to repo root) ────────────────────────────────────────────
BASE          = "experiments/daemon"
INBOX         = os.path.join(BASE, "inbox")
OUTBOX        = os.path.join(BASE, "outbox")
LOG_DIR       = os.path.join(BASE, "logs")
SESSION_LOG   = os.path.join(LOG_DIR, "session.jsonl")
FINAL_SUMMARY = os.path.join(LOG_DIR, "final_summary.json")
SHUTDOWN_FLAG = os.path.join(BASE, "SHUTDOWN")
PID_FILE      = os.path.join(BASE, "daemon.pid")

for d in [INBOX, OUTBOX, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)

# ── shared state ──────────────────────────────────────────────────────────────
state = {
    "started_at":       datetime.now(timezone.utc).isoformat(),
    "prompts_received": 0,
    "prompts_answered": 0,
    "errors":           0,
    "total_tokens":     0,
    "total_elapsed_s":  0.0,
    "last_prompt_id":   None,
    "status":           "running",
}
state_lock = threading.Lock()


# ── hardware snapshot ─────────────────────────────────────────────────────────
def hw_snap() -> dict:
    snap = {"ts": datetime.now(timezone.utc).isoformat()}
    try:
        import psutil
        vm = psutil.virtual_memory()
        snap["ram_used_gb"]  = round(vm.used  / 1024**3, 2)
        snap["ram_total_gb"] = round(vm.total / 1024**3, 2)
        snap["cpu_pct"]      = psutil.cpu_percent(interval=0.1)
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.urlopen(f"{ENDPOINT}/models", timeout=2)
        data = json.loads(req.read())
        snap["lemonade_loaded"] = [m["id"] for m in data.get("data", [])]
    except Exception:
        snap["lemonade_loaded"] = []
    return snap


# ── logger ────────────────────────────────────────────────────────────────────
def log_event(event: dict):
    """Append a JSON event line to session.jsonl"""
    event["_ts"] = datetime.now(timezone.utc).isoformat()
    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ── /status HTTP handler ──────────────────────────────────────────────────────
class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            with state_lock:
                body = json.dumps(state, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress access log spam


def run_status_server():
    server = HTTPServer(("127.0.0.1", STATUS_PORT), StatusHandler)
    server.serve_forever()


# ── model call ────────────────────────────────────────────────────────────────
def call_model(prompt: str, prompt_id: str) -> dict:
    """Send prompt to model, return structured result dict."""
    hw_pre = hw_snap()
    t0     = time.perf_counter()
    error  = None
    raw    = ""
    tokens = 0
    finish = "unknown"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            timeout=CALL_TIMEOUT,
        )
        if response.choices:
            choice = response.choices[0]
            raw    = (choice.message.content or "") if choice.message else ""
            finish = choice.finish_reason or "unknown"
        tokens = response.usage.total_tokens if response.usage else 0
    except Exception as e:
        error = str(e)

    elapsed  = round(time.perf_counter() - t0, 3)
    hw_post  = hw_snap()

    return {
        "prompt_id":  prompt_id,
        "prompt":     prompt,
        "response":   raw,
        "tokens":     tokens,
        "elapsed_s":  elapsed,
        "finish":     finish,
        "error":      error,
        "hw_pre":     hw_pre,
        "hw_post":    hw_post,
        "tok_per_s":  round(tokens / elapsed, 1) if elapsed > 0 and tokens > 0 else None,
    }


# ── inbox watcher ─────────────────────────────────────────────────────────────
processed = set()

def process_inbox():
    """
    Scan inbox/ for *.txt prompt files not yet processed.
    Each file: plain text prompt. Prompt ID derived from filename stem.
    Response written to outbox/<prompt_id>.txt
    """
    files = sorted(
        f for f in os.listdir(INBOX)
        if f.endswith(".txt") and f not in processed
    )
    for fname in files:
        prompt_id = fname.replace(".txt", "")
        prompt_path = os.path.join(INBOX, fname)

        with open(prompt_path, "r", encoding="utf-8") as pf:
            prompt = pf.read().strip()

        if not prompt:
            processed.add(fname)
            continue

        print(f"[daemon] → prompt: {prompt_id}")

        with state_lock:
            state["prompts_received"] += 1
            state["last_prompt_id"]    = prompt_id

        result = call_model(prompt, prompt_id)

        # write response to outbox
        out_path = os.path.join(OUTBOX, f"{prompt_id}.txt")
        with open(out_path, "w", encoding="utf-8") as of:
            if result["error"]:
                of.write(f"ERROR: {result['error']}")
            else:
                of.write(result["response"])

        # update state
        with state_lock:
            if result["error"]:
                state["errors"] += 1
            else:
                state["prompts_answered"] += 1
            state["total_tokens"]    += result["tokens"]
            state["total_elapsed_s"] += result["elapsed_s"]

        # log event
        log_event({"event": "prompt_handled", **result})

        print(f"[daemon] ← answer: {prompt_id}  "
              f"tokens={result['tokens']}  elapsed={result['elapsed_s']}s  "
              f"tok/s={result['tok_per_s']}  error={result['error']}")

        processed.add(fname)


# ── shutdown ──────────────────────────────────────────────────────────────────
def shutdown():
    with state_lock:
        state["status"]    = "shutdown"
        state["ended_at"]  = datetime.now(timezone.utc).isoformat()
        final = dict(state)

    log_event({"event": "daemon_shutdown", "state": final})

    with open(FINAL_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2)

    print(f"[daemon] final summary → {FINAL_SUMMARY}")
    print(f"[daemon] session log   → {SESSION_LOG}")
    print(f"[daemon] shutting down — bye")

    # remove pid file
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


# ── main loop ─────────────────────────────────────────────────────────────────
def main():
    # write pid
    with open(PID_FILE, "w") as pf:
        pf.write(str(os.getpid()))

    print(f"[daemon] started  model={MODEL}  pid={os.getpid()}")
    print(f"[daemon] inbox    → {INBOX}")
    print(f"[daemon] outbox   → {OUTBOX}")
    print(f"[daemon] status   → http://localhost:{STATUS_PORT}/status")
    print(f"[daemon] shutdown → create {SHUTDOWN_FLAG}")

    log_event({"event": "daemon_start", "model": MODEL, "pid": os.getpid(),
               "hw": hw_snap()})

    # start /status server in background thread
    t = threading.Thread(target=run_status_server, daemon=True)
    t.start()
    print(f"[daemon] status server listening on :{STATUS_PORT}")

    # main poll loop
    while True:
        if os.path.exists(SHUTDOWN_FLAG):
            print("[daemon] SHUTDOWN flag detected")
            log_event({"event": "shutdown_flag_detected",
                       "flag": SHUTDOWN_FLAG})
            os.remove(SHUTDOWN_FLAG)
            break

        try:
            process_inbox()
        except Exception as e:
            print(f"[daemon] inbox error: {e}")
            log_event({"event": "inbox_error", "error": str(e)})

        time.sleep(POLL_S)

    shutdown()


if __name__ == "__main__":
    main()
