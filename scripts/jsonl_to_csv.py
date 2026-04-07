# scripts/jsonl_to_csv.py — T10
# Toolbox entry: convert a JSONL audit log to CSV.
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
