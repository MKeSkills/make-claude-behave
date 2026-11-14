"""Run every self-test in this folder. Prints each test's lines, then "ok"
when all pass (exit 0), or the names of those that failed (exit 1)."""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    # The self-tests print non-ASCII text (curly quotes, dashes). Ask each
    # child for UTF-8 output and read it as UTF-8, so a console code page such
    # as cp1252 on Windows cannot break the run or hide a test's lines.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    failed = []
    tests = sorted(HERE.glob("selftest_*.py"))
    for test in tests:
        print(f"== {test.name}")
        out = subprocess.run([sys.executable, str(test)], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", env=env)
        print((out.stdout or "").rstrip())
        if (out.stderr or "").strip():
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
