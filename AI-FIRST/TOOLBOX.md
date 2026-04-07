# 🧾 Fractal Claws — Memory Toolbox

> **AI-FIRST DOC** — A curated library of reusable algorithms, scripts, and
> patterns the coding agent (Cline / Luffy) can call directly to solve common
> problems without re-deriving them from scratch.
>
> **How to use:** When decomposing a ticket, check this file first.
> If a matching script exists in `scripts/`, reference it instead of writing new code.
> If you write a new reusable solution, add it here and commit.

---

## Index

| ID | Category | Script | What it solves |
|---|---|---|---|
| T01 | File I/O | `scripts/scan_yaml_dir.py` | Load all YAML files from a directory as dicts |
| T02 | File I/O | `scripts/safe_move.py` | Atomically move a file, create dst dir if missing |
| T03 | Text | `scripts/word_frequency.py` | Count word frequency in a text file, output Markdown table |
| T04 | Process | `scripts/run_pytest_gate.py` | Run a pytest gate file, return pass/fail + full output |
| T05 | Git | `scripts/git_commit_push.py` | Stage all, commit with message, push to origin/main |
| T06 | Logging | `scripts/append_jsonl.py` | Append a dict as a JSONL line to a log file |
| T07 | Validation | `scripts/validate_ticket_yaml.py` | Check a YAML file has required ticket fields |
| T08 | Network | `scripts/ping_mesh_node.py` | Ping a Meshtastic node by node ID, return latency |
| T09 | Crypto | `scripts/sha256_file.py` | Compute SHA-256 of a file, return hex digest |
| T10 | Data | `scripts/jsonl_to_csv.py` | Convert a JSONL log to CSV for analysis |

---

## T01 — Scan YAML Directory

**File:** `scripts/scan_yaml_dir.py`  
**Use when:** You need to load all tickets or config files from a folder.

```python
# scripts/scan_yaml_dir.py
import glob, yaml, sys

def scan_yaml_dir(directory: str) -> list[dict]:
    results = []
    for path in sorted(glob.glob(f"{directory}/*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if data:
                data["_path"] = path
                results.append(data)
        except Exception as e:
            print(f"[SKIP] {path}: {e}")
    return results

if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "tickets/open"
    items = scan_yaml_dir(directory)
    print(f"Loaded {len(items)} files from {directory}")
    for item in items:
        print(f"  {item.get('ticket_id', item.get('_path'))}")
```

---

## T02 — Safe Move

**File:** `scripts/safe_move.py`  
**Use when:** Moving a ticket from `open/` to `closed/` or `failed/`.

```python
# scripts/safe_move.py
import os, shutil, sys

def safe_move(src: str, dst_dir: str) -> str:
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source not found: {src}")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.move(src, dst)
    return dst

if __name__ == "__main__":
    src, dst_dir = sys.argv[1], sys.argv[2]
    new_path = safe_move(src, dst_dir)
    print(f"Moved: {src} -> {new_path}")
```

---

## T03 — Word Frequency

**File:** `scripts/word_frequency.py`  
**Use when:** A ticket asks for word frequency analysis on any text file.

```python
# scripts/word_frequency.py
import re, sys
from collections import Counter

def word_frequency(path: str, top_n: int = 10) -> list[tuple[str, int]]:
    with open(path) as f:
        text = f.read().lower()
    words = re.findall(r"\b[a-z]+\b", text)
    return Counter(words).most_common(top_n)

if __name__ == "__main__":
    path = sys.argv[1]
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    results = word_frequency(path, top_n)
    print(f"## Top Words\n")
    print("| Word | Count |")
    print("|------|-------|")
    for word, count in results:
        print(f"| {word} | {count} |")
    print(f"\nTotal unique words: {len(set(w for w,_ in results))}")
```

---

## T04 — Run Pytest Gate

**File:** `scripts/run_pytest_gate.py`  
**Use when:** Running any validation gate test file.

```python
# scripts/run_pytest_gate.py
import subprocess, sys, os

def run_gate(test_file: str, repo_root: str = None) -> int:
    if repo_root:
        os.chdir(repo_root)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "-q"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr.strip():
        print("STDERR:", result.stderr)
    return result.returncode

if __name__ == "__main__":
    test_file = sys.argv[1] if len(sys.argv) > 1 else "tests/"
    repo_root = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(run_gate(test_file, repo_root))
```

Example call from Cline:
```bash
python scripts/run_pytest_gate.py tests/test_ticket_io.py
```

---

## T05 — Git Commit and Push

**File:** `scripts/git_commit_push.py`  
**Use when:** A ticket's Step 4 requires committing and pushing results.

```python
# scripts/git_commit_push.py
import subprocess, sys

def git_commit_push(message: str, remote: str = "origin", branch: str = "main") -> int:
    steps = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", message],
        ["git", "push", remote, branch],
    ]
    for cmd in steps:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"[FAIL] {' '.join(cmd)}\n{result.stderr}")
            return result.returncode
    return 0

if __name__ == "__main__":
    message = sys.argv[1] if len(sys.argv) > 1 else "chore: automated commit"
    sys.exit(git_commit_push(message))
```

Example call:
```bash
python scripts/git_commit_push.py "gate: GATE-STEP-01 PASS — all ticket_io tests green"
```

---

## T06 — Append JSONL

**File:** `scripts/append_jsonl.py`  
**Use when:** Logging an attempt, result, or event to an audit file.

```python
# scripts/append_jsonl.py
import json, os, time, sys

def append_jsonl(path: str, record: dict) -> None:
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

if __name__ == "__main__":
    path = sys.argv[1]
    record = json.loads(sys.argv[2])
    append_jsonl(path, record)
    print(f"Appended to {path}")
```

---

## T07 — Validate Ticket YAML

**File:** `scripts/validate_ticket_yaml.py`  
**Use when:** Checking a ticket file before handing it to the runner.

```python
# scripts/validate_ticket_yaml.py
import yaml, sys

REQUIRED = ["ticket_id", "task", "status"]

def validate(path: str) -> list[str]:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return [f for f in REQUIRED if f not in data or data[f] is None]

if __name__ == "__main__":
    path = sys.argv[1]
    missing = validate(path)
    if missing:
        print(f"[INVALID] {path} missing: {missing}")
        sys.exit(1)
    print(f"[VALID] {path}")
```

---

## T08 — Ping Mesh Node

**File:** `scripts/ping_mesh_node.py`  
**Use when:** Checking if a Meshtastic node is reachable on the mesh.

```python
# scripts/ping_mesh_node.py
# Requires: pip install meshtastic
import sys, time

def ping_node(node_id: str, interface_port: str = None) -> dict:
    try:
        import meshtastic
        import meshtastic.serial_interface
        iface = meshtastic.serial_interface.SerialInterface(interface_port)
        start = time.time()
        # Send a ping traceroute to the node
        iface.sendPing(node_id)
        latency = round((time.time() - start) * 1000, 2)
        iface.close()
        return {"node_id": node_id, "reachable": True, "latency_ms": latency}
    except Exception as e:
        return {"node_id": node_id, "reachable": False, "error": str(e)}

if __name__ == "__main__":
    node_id = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else None
    result = ping_node(node_id, port)
    print(result)
```

---

## T09 — SHA-256 File Hash

**File:** `scripts/sha256_file.py`  
**Use when:** Verifying file integrity before/after a ticket operation.

```python
# scripts/sha256_file.py
import hashlib, sys

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

if __name__ == "__main__":
    path = sys.argv[1]
    digest = sha256_file(path)
    print(f"{digest}  {path}")
```

---

## T10 — JSONL to CSV

**File:** `scripts/jsonl_to_csv.py`  
**Use when:** Converting attempt logs to CSV for analysis or reporting.

```python
# scripts/jsonl_to_csv.py
import json, csv, sys

def jsonl_to_csv(src: str, dst: str) -> int:
    rows = []
    with open(src) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        print("No records found.")
        return 0
    keys = list(rows[0].keys())
    with open(dst, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {dst}")
    return len(rows)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    jsonl_to_csv(src, dst)
```

---

## Adding New Tools

When you write a reusable script that solves a general problem:

1. Save it to `scripts/<name>.py`
2. Add a row to the Index table above
3. Add a full section (ID, use-when, code block, example call)
4. Commit: `git commit -m "toolbox: add T## — <short description>"`

The toolbox grows with the system. Every ticket that produces a reusable
solution should deposit it here so the next ticket can find it.

---

*Last updated: 2026-04-07*
