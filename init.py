#!/usr/bin/env python3
"""
init.py — BuddingBot bootstrap.

Usage:
    python init.py "<goal>"
    python init.py "<goal>" --stage bud
    python init.py "<goal>" --model Qwen3.5-4B-GGUF

What it does:
  1. Validates the environment (calls pre_flight.py)
  2. Writes settings.yaml with goal + stage + model
  3. Fires parent_agent.py with the goal

To clone and start a new bot:
    cp -r Fractal_Claws/ MyNewBot/
    cd MyNewBot/
    python init.py "your goal here"
"""
import sys
import os
import subprocess
import argparse
import yaml
import time

DEFAULT_STAGE = "bud"
DEFAULT_MODEL = "Qwen3.5-4B-GGUF"
SETTINGS_PATH = "settings.yaml"


def banner(goal: str, stage: str, model: str):
    print("")
    print("╔══════════════════════════════════════════╗")
    print("║          BuddingBot Bootstrap            ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  goal  : {goal}")
    print(f"  stage : {stage}")
    print(f"  model : {model}")
    print(f"  time  : {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    print("")


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


def patch_settings(goal: str, stage: str, model: str):
    data = {}
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    data.setdefault("agent", {})
    data["agent"]["stage"]        = stage
    data["agent"]["current_goal"] = goal
    data["agent"]["started_at"]   = time.strftime("%Y-%m-%dT%H:%M:%S")

    data.setdefault("models", {})
    data["models"]["child"] = model

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    print(f"[init] settings.yaml updated (stage={stage}, model={model})")


def fire_parent(goal: str) -> int:
    parent = os.path.join("agent", "parent_agent.py")
    if not os.path.exists(parent):
        print(f"[init] FAIL: {parent} not found")
        return 1
    print(f"[init] firing parent_agent.py...")
    result = subprocess.run([sys.executable, parent, "--goal", goal])
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="BuddingBot bootstrap")
    parser.add_argument("goal", nargs="?", help="The goal for the bot")
    parser.add_argument("--stage", default=DEFAULT_STAGE,
                        choices=["bud", "branch", "planted", "rooted"],
                        help=f"Bot stage (default: {DEFAULT_STAGE})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Child model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Skip pre_flight.py check")
    args = parser.parse_args()

    if not args.goal:
        parser.print_help()
        print("\nExample:")
        print('  python init.py "write a fibonacci script and verify it runs"')
        sys.exit(0)

    banner(args.goal, args.stage, args.model)

    if not args.skip_preflight:
        if not run_preflight():
            sys.exit(1)

    patch_settings(args.goal, args.stage, args.model)

    rc = fire_parent(args.goal)
    if rc != 0:
        print(f"[init] parent exited with code {rc}")
        sys.exit(rc)
    print("[init] done")


if __name__ == "__main__":
    main()
