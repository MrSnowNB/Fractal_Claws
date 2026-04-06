"""
pre_flight.py — Lemonade inference readiness gate.

Usage:
    python pre_flight.py                          # uses DEFAULT_MODEL
    python pre_flight.py Qwen3-Coder-Next-GGUF    # override model via arg

Run this after ANY model swap in Lemonade UI before using Cline or the harness.
The /api/v1/models list updates before inference is ready — only a real
chat/completions call confirms the model is warm.
"""

import sys
import time
import openai

BASE_URL = "http://localhost:8000/api/v1"
API_KEY  = "x"
MAX_RETRIES = 15
RETRY_DELAY = 8  # seconds

DEFAULT_MODEL = "user.Hermes-3-Llama-3.1-8B-GGUF"

KNOWN_MODELS = {
    "hermes":  "user.Hermes-3-Llama-3.1-8B-GGUF",
    "qwen":    "Qwen3-Coder-Next-GGUF",
    "35b":     "Qwen3.5-35B-A3B-GGUF",
    "a3b":     "Qwen3.5-35B-A3B-GGUF",
}

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
