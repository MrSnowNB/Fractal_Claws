# scripts/append_jsonl.py — T06
# Toolbox entry: append a dict as a JSONL line to an audit log file.
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
