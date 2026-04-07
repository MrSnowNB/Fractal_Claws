"""
pre_flight.py — Inference readiness gate + Cline settings sync.

Hardware: HP ZBook (single node)
Endpoint: Lemonade at http://localhost:8000/api/v1

Active harness models:
  Parent (Cline):  Qwen3-Coder-Next-GGUF  (~80B, orchestrator)
  Child (runner):  Qwen3.5-35B-A3B-GGUF   (executor, default probe target)

DEPRECATED: Qwen3.5-4B-GGUF — deferred to future integration phase.
  Do not reference 4B in active runs.

Usage:
    python pre_flight.py                        # probe A3B (default)
    python pre_flight.py a3b                    # probe A3B explicitly
    python pre_flight.py Qwen3.5-35B-A3B-GGUF  # probe A3B by full ID

Probe sequence:
    1. /models list — confirms Lemonade is alive and model is in the loaded list
    2. generation_probe — sends max_tokens:1 to confirm model GENERATES
       (catches the 'downloaded but not loaded' failure class)
    3. READY call — confirms full response capability
    4. Cline settings sync
"""

import sys
import time
import json
import re
import openai
import urllib.request
from pathlib import Path

BASE_URL    = "http://localhost:8000/api/v1"
API_KEY     = "x"
MAX_RETRIES = 15
RETRY_DELAY = 8

# Default: child executor model (A3B)
DEFAULT_MODEL = "Qwen3.5-35B-A3B-GGUF"

KNOWN_MODELS = {
    "a3b":   "Qwen3.5-35B-A3B-GGUF",
    "35b":   "Qwen3.5-35B-A3B-GGUF",
    "next":  "Qwen3-Coder-Next-GGUF",
    "coder": "Qwen3-Coder-Next-GGUF",
    # 4B: DEPRECATED — deferred to future integration phase
    # "4b":  "Qwen3.5-4B-GGUF",
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
    key = arg.lower()
    if key == "4b":
        print("[pre_flight] WARNING: 4B model is DEPRECATED and deferred to future integration.")
        print("[pre_flight] Aborting — use 'python pre_flight.py' to probe the active A3B model.")
        sys.exit(1)
    return KNOWN_MODELS.get(key, arg)


def check_model_listed(model: str) -> bool:
    """Step 1: confirm model appears in /models loaded list."""
    try:
        req  = urllib.request.urlopen(f"{BASE_URL}/models", timeout=5)
        data = json.loads(req.read())
        loaded = [m["id"] for m in data.get("data", [])]
        if model in loaded:
            print(f"[pre_flight] /models OK — '{model}' is in loaded list")
            return True
        else:
            print(f"[pre_flight] /models: '{model}' NOT in loaded list.")
            print(f"[pre_flight] Loaded: {loaded}")
            print(f"[pre_flight] → Open Lemonade UI and load '{model}' before continuing.")
            return False
    except Exception as e:
        print(f"[pre_flight] /models call failed: {e}")
        return False


def generation_probe(client: openai.OpenAI, model: str) -> bool:
    """Step 2: send max_tokens:1 to confirm model GENERATES (not just lists).
    This surfaces the 'downloaded but not loaded in slot' failure class.
    A model that lists but doesn't generate returns empty choices here.
    """
    print(f"[pre_flight] generation probe (max_tokens=1)...")
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            temperature=0,
            timeout=30,
        )
        if r.choices and (r.choices[0].message.content or "").strip():
            print(f"[pre_flight] generation probe OK — model is generating")
            return True
        else:
            print(f"[pre_flight] generation probe FAILED — empty choices or empty content")
            print(f"[pre_flight] Model may be downloaded but not loaded into active slot.")
            print(f"[pre_flight] → In Lemonade UI: unload and reload '{model}'.")
            return False
    except Exception as e:
        print(f"[pre_flight] generation probe error: {e}")
        return False


def check(model: str) -> None:
    client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY)
    print(f"[pre_flight] Hardware:  HP ZBook (single node)")
    print(f"[pre_flight] Endpoint:  {BASE_URL}")
    print(f"[pre_flight] Model:     {model}")
    print(f"[pre_flight] Max wait:  {MAX_RETRIES * RETRY_DELAY}s\n")

    # Step 1 — model must appear in /models list
    if not check_model_listed(model):
        sys.exit(1)

    # Step 2 — generation probe (catches downloaded-but-not-loaded)
    if not generation_probe(client, model):
        sys.exit(1)

    # Step 3 — full READY check with retries
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with one word: READY"}],
                max_tokens=10,
                temperature=0,
            )
            reply = r.choices[0].message.content.strip()
            print(f"[pre_flight] READY — model responded: '{reply}'")
            update_cline_settings(model)
            print(f"[pre_flight] Safe to use Cline / harness now.")
            sys.exit(0)
        except openai.NotFoundError:
            print(f"[{attempt}/{MAX_RETRIES}] 404 — model not ready, waiting {RETRY_DELAY}s...")
        except openai.APIConnectionError as e:
            print(f"[{attempt}/{MAX_RETRIES}] Connection error — is Lemonade running on :8000? ({e})")
        except Exception as e:
            print(f"[{attempt}/{MAX_RETRIES}] Unexpected error: {e}")
        time.sleep(RETRY_DELAY)

    print(f"\n[pre_flight] FAILED — '{model}' never ready after {MAX_RETRIES * RETRY_DELAY}s.")
    print("[pre_flight] Check Lemonade UI — is the model loaded and generating?")
    sys.exit(1)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    model = resolve_model(arg)
    check(model)
