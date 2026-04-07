# scripts/git_commit_push.py — T05
# Toolbox entry: stage all changes, commit, and push to remote.
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
