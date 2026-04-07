#!/usr/bin/env python3
"""
init.py — Fractal Claws bootstrap.

Usage:
    python init.py "<goal>"
    python init.py "<goal>" --stage bud

What it does:
  1. Validates the environment (calls pre_flight.py)
  2. Writes agent.stage + agent.current_goal into settings.yaml
  3. Fires agent/runner.py with the goal

Model is configured in settings.yaml (model.id).
Do NOT pass --model 4b or Qwen3.5-4B-GGUF — that model is DEPRECATED.

To clone and start a new session:
    git pull
    python init.py "your goal here"
"""
import sys
import os
import subprocess
import argparse
import yaml
import time

DEFAULT_STAGE  = "bud"
# Model is read from settings.yaml — do NOT set a default here.
# 4B MODEL: DEPRECATED — init.py will reject it with sys.exit(1).
SETTINGS_PATH  = "settings.yaml"

DEPRECATED_MODELS = {
    "4b", "qwen3.5-4b-gguf", "qwen3.5-4b",
}


def banner(goal: str, stage: str, model: str):
    print("")
    print("╭────────────────────────────────────────────╮")
    print("│       Fractal Claws Bootstrap            │")
    print("╰────────────────────────────────────────────╯")
    print(f"  goal  : {goal}")
    print(f"  stage : {stage}")
    print(f"  model : {model} (from settings.yaml)")
    print(f"  time  : {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    print("")


def get_model_from_settings() -> str:
    if not os.path.exists(SETTINGS_PATH):
        return "<settings.yaml not found>"
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("model", {}).get("id", "<model.id not set>")
    except Exception:
        return "<could not read settings.yaml>"


def run_preflight() -> bool:
    if not os.path.exists("pre_flight.py"):
        print("[init] WARNING: pre_flight.py not found — skipping preflight")
        return True
    print("[init] running pre_flight.py...")
    result = subprocess.run([sys.executable, "pre_flight.py"], capture_output=False)
    if result.returncode != 0:
        print(f"[init] FAIL: pre_flight returned {result.returncode} — fix before proceeding")
        return False
    print("[init] preflight OK")
    return True


def patch_settings(goal: str, stage: str):
    data = {}
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    data.setdefault("agent", {})
    data["agent"]["stage"]        = stage
    data["agent"]["current_goal"] = goal
    data["agent"]["started_at"]   = time.strftime("%Y-%m-%dT%H:%M:%S")
    # Do NOT write model here — model.id is managed in settings.yaml only.

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    print(f"[init] settings.yaml updated (stage={stage})")


def fire_runner(goal: str) -> int:
    runner = os.path.join("agent", "runner.py")
    if not os.path.exists(runner):
        print(f"[init] FAIL: {runner} not found")
        return 1
    print(f"[init] firing agent/runner.py...")
    result = subprocess.run([sys.executable, runner, "--goal", goal])
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Fractal Claws bootstrap")
    parser.add_argument("goal", nargs="?", help="The goal for the session")
    parser.add_argument("--stage", default=DEFAULT_STAGE,
                        choices=["bud", "branch", "planted", "rooted"],
                        help=f"Session stage (default: {DEFAULT_STAGE})")
    parser.add_argument("--model", default=None,
                        help="DEPRECATED — model is set in settings.yaml. Passing 4B will abort.")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Skip pre_flight.py check")
    args = parser.parse_args()

    # Hard-block 4B
    if args.model and args.model.lower().replace("-gguf", "").replace("qwen3.5-", "") in DEPRECATED_MODELS \
            or (args.model and args.model.lower() in DEPRECATED_MODELS):
        print("[init] ABORT: Qwen3.5-4B-GGUF is DEPRECATED — deferred to future integration phase.")
        print("[init] Model is configured in settings.yaml. Do not pass --model 4b.")
        sys.exit(1)

    if args.model:
        print(f"[init] WARNING: --model flag is deprecated. Model is set in settings.yaml.")
        print(f"[init] Ignoring --model {args.model} — using settings.yaml model.id instead.")

    if not args.goal:
        parser.print_help()
        print("\nExample:")
        print('  python init.py "write a fibonacci script and verify it runs"')
        sys.exit(0)

    model = get_model_from_settings()
    banner(args.goal, args.stage, model)

    if not args.skip_preflight:
        if not run_preflight():
            sys.exit(1)

    patch_settings(args.goal, args.stage)

    rc = fire_runner(args.goal)
    if rc != 0:
        print(f"[init] runner exited with code {rc}")
        sys.exit(rc)
    print("[init] done")


if __name__ == "__main__":
    main()
