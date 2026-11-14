"""Self-test for check_lesson_commit.py. Run with any Python 3.9+ and git on
the PATH; every line says "ok", and the last line is "ok" when all cases pass
(exit 0).

Part 1 calls the check's function on sample diffs. Part 2 installs the check
as a real commit-msg hook in a throwaway git repository and makes commits,
so the refusals are seen coming from git itself."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "check_lesson_commit.py"
sys.path.insert(0, str(HERE.parent))
sys.dont_write_bytecode = True
import check_lesson_commit as clc  # noqa: E402

L = clc.LESSONS
ENTRY_A = "- **2025-01-14, a script stated the wrong time zone.** It printed UTC. Status: open."
ENTRY_B = "- **2025-01-20, a hook was never registered.** Its tests passed. Status: open."


def diff(removed=(), added=()):
    return "\n".join([f"--- a/{L}", f"+++ b/{L}"] + [f"-{l}" for l in removed]
                     + [f"+{l}" for l in added])


UNIT = [
    # (description, message, staged, diff, refused?)
    ("a new entry alone", "Record a lesson", [L], diff(added=[ENTRY_A]), True),
    ("a new entry with a hook", "Record a lesson", [L, ".claude/hooks/guard.py"],
     diff(added=[ENTRY_A]), False),
    ("a new entry with a registered hook (settings only)", "Register", [L, ".claude/settings.json"],
     diff(added=[ENTRY_A]), False),
    ("a new entry with only a document beside it", "Record", [L, "README.md"],
     diff(added=[ENTRY_A]), True),
    ("a new entry with a Lesson-fix reason",
     "Record\n\nLesson-fix: none - no tool call shows this mistake", [L], diff(added=[ENTRY_A]), False),
    ("a Lesson-fix line with no real reason", "Record\n\nLesson-fix: none - n/a", [L],
     diff(added=[ENTRY_A]), True),
    ("a note added to an entry, alone", "Note",
     [L], diff(removed=[ENTRY_A], added=[ENTRY_A[:-14] + " Again 2025-02-01: twice. Status: open."]), True),
    ("an entry marked fixed", "Mark fixed", [L],
     diff(removed=[ENTRY_A], added=[ENTRY_A.replace("Status: open.",
                                                     "Status: fixed 2025-01-15, enforced by the guard.")]),
     False),
    ("an entry rewrapped over two lines", "Rewrap", [L],
     diff(removed=[ENTRY_A], added=[ENTRY_A[:60], "  " + ENTRY_A[60:]]), False),
    ("an entry removed", "Tidy", [L], diff(removed=[ENTRY_A, ENTRY_B], added=[ENTRY_B]), True),
    ("an entry removed while another is added, with a hook", "Swap", [L, "hooks/x.py"],
     diff(removed=[ENTRY_A], added=[ENTRY_B]), True),
    ("a commit that does not touch the lessons file", "Code", ["src/app.py"], "", False),
]


def git(repo, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=Self Test", "-c", "user.email=selftest@example.invalid",
                           *args], cwd=repo, capture_output=True, text=True, check=check)


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def commit(repo, message):
    git(repo, "add", "-A")
    out = git(repo, "commit", "-q", "-m", message, check=False)
    return out.returncode == 0, out.stderr


def main():
    bad = 0
    for name, message, staged, lessons_diff, refused in UNIT:
        got = bool(clc.problems(message, staged, lessons_diff))
        ok = got == refused
        bad += not ok
        print("ok  " if ok else "BAD ", f"refused={got!s:5} {name}")

    with tempfile.TemporaryDirectory() as repo:
        git(repo, "init", "-q")
        hook = (f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" '
                f'"{SCRIPT.as_posix()}" "$1"\n')
        write(repo, ".githooks/commit-msg", hook)
        os.chmod(Path(repo) / ".githooks" / "commit-msg", 0o755)
        git(repo, "config", "core.hooksPath", ".githooks")
        head = "# Lessons\n\n## Lessons\n\n"
        steps = [
            ("git: the empty lessons file", {L: head}, "Start", True),
            ("git: an entry with no fix is refused", {L: head + ENTRY_A + "\n"}, "Record", False),
            ("git: the same with a Lesson-fix reason goes in", {L: head + ENTRY_A + "\n"},
             "Record\n\nLesson-fix: none - no tool call shows this mistake", True),
            ("git: a second entry with its hook goes in",
             {L: head + ENTRY_B + "\n" + ENTRY_A + "\n", ".claude/hooks/check.py": "print('ok')\n"},
             "Record with fix", True),
            ("git: removing an entry is refused", {L: head + ENTRY_B + "\n"}, "Tidy", False),
            ("git: marking it fixed goes in",
             {L: head + ENTRY_B + "\n" + ENTRY_A.replace(
                 "Status: open.", "Status: fixed 2025-01-15, enforced by the guard.") + "\n"},
             "Mark fixed", True),
        ]
        for name, files, message, accepted in steps:
            for rel, text in files.items():
                write(repo, rel, text)
            got, err = commit(repo, message)
            ok = got == accepted and (accepted or "commit refused" in err)
            bad += not ok
            print("ok  " if ok else "BAD ", f"committed={got!s:5} {name}")
            if not got:
                git(repo, "reset", "-q", "--hard", "HEAD")
        out = git(repo, "log", "--format=%s")
        ok = out.stdout.split() == ["Mark", "fixed", "Record", "with", "fix", "Record", "Start"]
        bad += not ok
        print("ok  " if ok else "BAD ", "git history holds exactly the accepted commits")
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
