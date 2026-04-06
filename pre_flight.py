"""
pre_flight.py — Lemonade inference readiness gate + Cline settings sync.

Usage:
    python pre_flight.py                          # uses DEFAULT_MODEL
    python pre_flight.py qwen                     # alias
    python pre_flight.py Qwen3-Coder-Next-GGUF    # full model ID

Run this after ANY model swap in Lemonade UI before using Cline or the harness.
On success, automatically updates VSCode settings.json so Cline uses the
correct model — no manual UI change needed.
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
RETRY_DELAY = 8  # seconds

DEFAULT_MODEL = "Qwen3-Coder-Next-GGUF"

KNOWN_MODELS = {
    "hermes": "user.Hermes-3-Llama-3.1-8B-GGUF",
    "qwen":   "Qwen3-Coder-Next-GGUF",
<<<<<<< HEAD
    "4b":     "Qwen3.5-4B-GGUF",       # ← child node
=======
>>>>>>> cd9ed7f3b7be83a41207d0ed364f4dca246da421
    "35b":    "Qwen3.5-35B-A3B-GGUF",
    "a3b":    "Qwen3.5-35B-A3B-GGUF",
}

<<<<<<< HEAD
  # ← corrected
=======
# VSCode settings.json locations — checked in order, first found wins
SETTINGS_PATHS = [
    Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json",
    Path.home() / ".config" / "Code" / "User" / "settings.json",  # Linux
    Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",  # macOS
]

# Cline settings.json key for the model ID
CLINE_MODEL_KEY = "cline.apiModelId"


def find_settings() -> Path | None:
    for p in SETTINGS_PATHS:
        if p.exists():
            return p
    return None


def update_cline_settings(model: str) -> None:
    path = find_settings()
    if not path:
        print("[pre_flight] ⚠ Could not find VSCode settings.json — update Cline model manually.")
        return

    try:
        raw = path.read_text(encoding="utf-8")

        # settings.json may have comments (JSONC) — strip // comments for parsing
        stripped = re.sub(r'(?m)^\s*//.*$', '', raw)
        stripped = re.sub(r',\s*([}\]])', r'\1', stripped)  # trailing commas

        data = json.loads(stripped)
        old = data.get(CLINE_MODEL_KEY, "<not set>")
        data[CLINE_MODEL_KEY] = model

        # Write back — pretty-printed, preserving indent style
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        print(f"[pre_flight] ✓ Cline settings updated: '{old}' → '{model}'")
        print(f"[pre_flight]   ({path})")
    except Exception as e:
        print(f"[pre_flight] ⚠ Failed to update settings.json: {e}")
        print(f"[pre_flight]   Set '{CLINE_MODEL_KEY}': '{model}' manually.")

>>>>>>> cd9ed7f3b7be83a41207d0ed364f4dca246da421

def resolve_model(arg: str) -> str:
    return KNOWN_MODELS.get(arg.lower(), arg)


def check(model: str) -> None:
    client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY)
    print(f"[pre_flight] Checking inference readiness for: {model}")
    print(f"[pre_flight] Max wait: {MAX_RETRIES * RETRY_DELAY}s ({MAX_RETRIES} attempts x {RETRY_DELAY}s)\n")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with one word: READY"}],
                max_tokens=10,
                temperature=0,
            )
            reply = r.choices[0].message.content.strip()
            print(f"[pre_flight] ✓ READY — model responded: '{reply}'")
            update_cline_settings(model)
            print(f"[pre_flight] Safe to use Cline / harness now.")
            sys.exit(0)
        except openai.NotFoundError:
            print(f"[{attempt}/{MAX_RETRIES}] 404 — inference slot not ready yet, waiting {RETRY_DELAY}s...")
        except openai.APIConnectionError as e:
            print(f"[{attempt}/{MAX_RETRIES}] Connection error — is Lemonade running? ({e})")
        except Exception as e:
            print(f"[{attempt}/{MAX_RETRIES}] Unexpected error: {e}")
        time.sleep(RETRY_DELAY)

    print(f"\n[pre_flight] FAILED — '{model}' never became inference-ready after {MAX_RETRIES * RETRY_DELAY}s.")
    print("[pre_flight] Check Lemonade UI — is the model fully loaded (green dot, stable RAM)?")
    sys.exit(1)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    model = resolve_model(arg)
    check(model)
