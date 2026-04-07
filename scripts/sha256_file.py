# scripts/sha256_file.py — T09
# Toolbox entry: compute SHA-256 digest of a file.
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
