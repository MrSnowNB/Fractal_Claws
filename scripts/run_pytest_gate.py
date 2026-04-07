# scripts/run_pytest_gate.py — T04
# Toolbox entry: run a pytest gate file and return exit code.
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
