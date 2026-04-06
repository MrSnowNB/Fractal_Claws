#!/usr/bin/env python3
"""
Debug script — dumps the raw Lemonade response so we can see
where the model output lives (content vs reasoning_content vs choices[0].message).
"""
import json
from openai import OpenAI

MODEL    = "Qwen3.5-4B-GGUF"
ENDPOINT = "http://localhost:8000/api/v1"
API_KEY  = "x"

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "Reply concisely."},
        {"role": "user",   "content": "Say: HELLO"},
    ],
    max_tokens=300,
    temperature=0.2,
)

print("=== response.choices[0].message ===")
msg = response.choices[0].message
print(f"  content          : {repr(msg.content)}")
print(f"  role             : {repr(msg.role)}")

# Qwen3 / Lemonade may put thinking in a non-standard field
if hasattr(msg, 'reasoning_content'):
    print(f"  reasoning_content: {repr(str(msg.reasoning_content)[:300])}")
if hasattr(msg, 'thinking'):
    print(f"  thinking         : {repr(str(msg.thinking)[:300])}")

print("\n=== full message dict ===")
try:
    print(json.dumps(msg.model_dump(), indent=2, default=str))
except Exception as e:
    print(f"  model_dump failed: {e}")
    print(f"  dir(msg): {[x for x in dir(msg) if not x.startswith('_')]}")

print("\n=== finish_reason ===")
print(f"  {response.choices[0].finish_reason}")
print("\n=== usage ===")
print(f"  {response.usage}")
