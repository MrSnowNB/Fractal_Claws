# scripts/safe_move.py — T02
# Toolbox entry: atomically move a file to a destination directory.
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
