# scripts/scan_yaml_dir.py — T01
# Toolbox entry: scan a directory for YAML files and return as list of dicts.
import glob, yaml, sys

def scan_yaml_dir(directory: str) -> list:
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
