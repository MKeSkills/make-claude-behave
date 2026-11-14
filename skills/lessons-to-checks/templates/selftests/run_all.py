"""Run every self-test in this folder. Prints each test's lines, then "ok"
when all pass (exit 0), or the names of those that failed (exit 1)."""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    failed = []
    tests = sorted(HERE.glob("selftest_*.py"))
    for test in tests:
        print(f"== {test.name}")
        out = subprocess.run([sys.executable, str(test)], capture_output=True, text=True, env=env)
        print(out.stdout.rstrip())
        if out.stderr.strip():
            print(out.stderr.rstrip())
        if out.returncode != 0:
            failed.append(test.name)
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    print(f"ok (all {len(tests)} self-tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
