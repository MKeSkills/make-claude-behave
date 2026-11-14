"""Self-test for check_lessons_mapped.py. Run with any Python 3.9+; every
line says "ok", and the last line is "ok" when all cases pass (exit 0).

The last case runs the check on this skill itself: its lessons.md against
its procedures/ folder."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
SCRIPT = HERE.parent / "check_lessons_mapped.py"
sys.path.insert(0, str(HERE.parent))
sys.dont_write_bytecode = True
import check_lessons_mapped as m  # noqa: E402

LESSONS = """# Lessons

## Lessons

- **2025-01-20, a hook was built and tested but never
  registered.** What happened. Status: fixed.

- **2025-01-14, a script stated the wrong time zone.** What happened.
  Status: open.
"""


def proc(*lines):
    return "# A procedure\n\n1. A step.\n\n" + m.HEADING + "\n\nIntro.\n\n" + "\n".join(lines) + "\n"


CASES = [
    ("both lessons placed, one name wrapped over two lines", {
        "build.md": proc("- **2025-01-20, a hook was built and tested but never",
                         "  registered.** Run the check. Check: check_hooks_registered.py."),
        "shell.md": proc("- **2025-01-14, a script stated the wrong time zone** Use the guard."),
    }, []),
    ("a lesson placed nowhere", {
        "build.md": proc("- **2025-01-20, a hook was built and tested but never registered.** x"),
    }, ["MISSING: 2025-01-14, a script stated the wrong time zone"]),
    ("a line with a typo", {
        "build.md": proc("- **2025-01-20, a hook was built and tested but never registered.** x",
                         "- **2025-01-14, a script stated the wrong tme zone.** y"),
    }, ["MISSING: 2025-01-14, a script stated the wrong time zone",
        "UNKNOWN: build.md: 2025-01-14, a script stated the wrong tme zone"]),
    ("a procedure without the section", {
        "build.md": proc("- **2025-01-20, a hook was built and tested but never registered.** x",
                         "- **2025-01-14, a script stated the wrong time zone.** y"),
        "other.md": "# Other\n\n1. A step.\n",
    }, ["NO SECTION: other.md"]),
    ("bold text in the steps does not count as placed", {
        "build.md": "# A procedure\n\n- **2025-01-14, a script stated the wrong time zone.** in a step\n\n"
                    + m.HEADING + "\n\n- **2025-01-20, a hook was built and tested but never registered.** x\n",
    }, ["MISSING: 2025-01-14, a script stated the wrong time zone"]),
]


def main():
    bad = 0
    for name, procedures, expected in CASES:
        got = m.problems(LESSONS, procedures)
        ok = got == expected
        bad += not ok
        print("ok  " if ok else "BAD ", name, "" if ok else f"-> {got}")
    out = subprocess.run([sys.executable, str(SCRIPT), "--lessons", str(SKILL / "lessons.md"),
                          "--procedures", str(SKILL / "procedures")], capture_output=True, text=True)
    ok = out.returncode == 0 and out.stdout.startswith("ok")
    bad += not ok
    print("ok  " if ok else "BAD ", "this skill's own lessons are each listed under a procedure",
          "" if ok else out.stdout)
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
