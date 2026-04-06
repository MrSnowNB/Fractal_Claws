"""
pre_flight.py — Inference readiness gate + Cline settings sync.

Hardware: HP ZBook (single node)
Endpoint: Lemonade at http://localhost:8000/api/v1

Usage:
    python pre_flight.py
    python pre_flight.py 4b
    python pre_flight.py Qwen3.5-4B-GGUF
"""

import sys
import time
import json
import re
import openai
from pathlib import Path

BASE_URL    = "http://localhost:8000/api/v1"
API_KEY     = "x"
MAX_RETRIES = 15
RETRY_DELAY = 8

DEFAULT_MODEL = "Qwen3.5-4B-GGUF"

KNOWN_MODELS = {
    "4b":   "Qwen3.5-4B-GGUF",
    "qwen": "Qwen3.5-4B-GGUF",
}

SETTINGS_PATHS = [
    Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json",
    Path.home() / ".config" / "Code" / "User" / "settings.json",
    Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",
]

CLINE_MODEL_KEY = "cline.apiModelId"


def find_settings() -> Path | None:
    for p in SETTINGS_PATHS:
        if p.exists():
            return p
    return None


def update_cline_settings(model: str) -> None:
    path = find_settings()
    if not path:
        print("[pre_flight] WARNING: Could not find VSCode settings.json.")
        return
    try:
        raw = path.read_text(encoding="utf-8")
        stripped = re.sub(r'(?m)^\s*//.*$', '', raw)
        stripped = re.sub(r',\s*([}\]])', r'\1', stripped)
        data = json.loads(stripped)
        old = data.get(CLINE_MODEL_KEY, "<not set>")
        data[CLINE_MODEL_KEY] = model
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        print(f"[pre_flight] Cline settings updated: '{old}' -> '{model}'")
    except Exception as e:
        print(f"[pre_flight] WARNING: Failed to update settings.json: {e}")


def resolve_model(arg: str) -> str:
    return KNOWN_MODELS.get(arg.lower(), arg)


def check(model: str) -> None:
    client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY)
    print(f"[pre_flight] Hardware:  HP ZBook (single node)")
    print(f"[pre_flight] Endpoint:  {BASE_URL}")
    print(f"[pre_flight] Model:     {model}")
    print(f"[pre_flight] Max wait:  {MAX_RETRIES * RETRY_DELAY}s\n")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with one word: READY"}],
                max_tokens=10,
                temperature=0,
            )
            reply = r.choices[0].message.content.strip()
            print(f"[pre_flight] READY - model responded: '{reply}'")
            update_cline_settings(model)
            print(f"[pre_flight] Safe to use Cline / harness now.")
            sys.exit(0)
        except openai.NotFoundError:
            print(f"[{attempt}/{MAX_RETRIES}] 404 - model not ready, waiting {RETRY_DELAY}s...")
        except openai.APIConnectionError as e:
            print(f"[{attempt}/{MAX_RETRIES}] Connection error - is Lemonade running on :8000? ({e})")
        except Exception as e:
            print(f"[{attempt}/{MAX_RETRIES}] Unexpected error: {e}")
        time.sleep(RETRY_DELAY)

    print(f"\n[pre_flight] FAILED - '{model}' never ready after {MAX_RETRIES * RETRY_DELAY}s.")
    print("[pre_flight] Check Lemonade UI - is the model loaded?")
    sys.exit(1)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    model = resolve_model(arg)
    check(model)
