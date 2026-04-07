#!/usr/bin/env python3
"""Debug script to test the exact decompose call that runner.py makes."""
import yaml
from openai import OpenAI

# Load settings
with open("settings.yaml", "r") as f:
    cfg = yaml.safe_load(f)

MODEL = cfg["model"]["id"]
ENDPOINT = cfg["model"]["endpoint"]
API_KEY = cfg["model"]["api_key"]
TEMPERATURE = float(cfg["model"].get("temperature", 0.2))
TIMEOUT = int(cfg["model"].get("timeout_seconds", 90))
MAX_RETRIES = int(cfg["model"].get("max_retries", 2))

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)

# Exact decompose prompt from runner.py
DECOMPOSE_SYSTEM = """\
You are a task decomposer. Output YAML tickets.

Rules:
- Each ticket: 1-2 tool calls. Tools: write_file, exec_python, read_file, list_dir.
- exec_python paths inside output/. write_file before exec_python on same path.
- Use depends_on for dependencies. Output ONLY valid YAML list.

Output format example:
- ticket_id: TASK-001
  title: "Generate Fibonacci"
  task: "Write script to generate first 20 fib numbers"
  depends_on: []
  allowed_tools: [write_file, exec_python]
"""

goal = "write a python script that generates the first 20 fibonacci numbers and saves them to output/fib.txt, then verify the file was written"

# Calculate budget like runner.py
decompose_budget = cfg["model"].get("decompose_budget")
if decompose_budget is None:
    context_window = cfg["model"].get("context_window", 8192)
    decompose_budget = int(context_window * 0.25)  # 25% buffer

print(f"Using decompose_budget: {decompose_budget}")

for attempt in range(1, MAX_RETRIES + 2):
    try:
        print(f"\n--- Attempt {attempt} ---")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": DECOMPOSE_SYSTEM},
                {"role": "user", "content": f"Goal: {goal}\nStart ticket numbering from TASK-001.\nOutput ONLY the YAML list."},
            ],
            max_tokens=decompose_budget,
            temperature=TEMPERATURE,
            timeout=TIMEOUT,
        )
        
        print(f"Response received!")
        print(f"Full response: {response}")
        print(f"Response type: {type(response)}")
        print(f"Choices: {response.choices}")
        
        if response.choices is None:
            print("ERROR: response.choices is None")
            continue
        
        print(f"Choices count: {len(response.choices)}")
        
        if not response.choices:
            print("ERROR: empty choices")
            continue
             
        choice = response.choices[0]
        print(f"Choice message: {choice.message}")
        print(f"Choice message type: {type(choice.message)}")
        
        if choice.message is None:
            print("ERROR: choice.message is None")
            continue
        
        raw = (choice.message.content or "") if choice.message else ""
        print(f"Raw content length: {len(raw)}")
        print(f"Raw content:\n{raw[:500]}")
        
        if not raw.strip():
            print("ERROR: empty content")
            continue
        
        print("SUCCESS: Got valid content!")
        break
        
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
        if attempt <= MAX_RETRIES:
            print(f"Retrying in 4s...")
            import time
            time.sleep(4)