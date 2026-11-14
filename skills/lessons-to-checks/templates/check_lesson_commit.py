"""commit-msg check: a lesson comes with its fix, and lessons are never removed.

Refuses a commit that:

1. adds a lesson to the lessons file (a new entry, or a note added to one:
   "Again ...", "again" with a date, "Update YYYY-MM-DD", "Repeated",
   "Recurred", "Seen again") without changing any file that can enforce it
   (a hook, a script, a test, other code, or the settings file that
   registers a hook), unless the message has a line
   `Lesson-fix: none - <why, at least 10 characters>`;
2. removes a lesson entry. A fixed lesson keeps its entry with
   "Status: fixed YYYY-MM-DD, enforced by <check>"; a canceled one with
   "Status: canceled YYYY-MM-DD" and the reason.

An entry is known by its first line: "- **YYYY-MM-DD, short name.**".
Rewording or rewrapping an entry, or changing its status line, keeps that
first line, so it is not a removal. A note counts only in text that is new
word by word, so rewrapping old text adds no note.

The check cannot tell whether the changed code is related to the lesson; the
reviewer of the commit checks that.

Install as a git hook (`.githooks/commit-msg`, with
`git config core.hooksPath .githooks`):

    #!/bin/sh
    exec python .claude/hooks/check_lesson_commit.py "$1"

Configure LESSONS and FIX below, or set LESSONS_FILE in the environment.
Standard library only.
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys

#: The lessons file, relative to the repository root.
LESSONS = os.environ.get("LESSONS_FILE", "docs/lessons.md")

#: A staged path that can enforce a lesson.
FIX = re.compile(
    r"\.(?:py|sh|bash|ps1|js|mjs|ts|go|rs|java|kt|rb|cs|php)$"
    r"|(?:^|/)\.claude/settings(?:\.local)?\.json$"
    r"|(?:^|/)\.githooks/")

#: An entry's first line: its date and name, up to the closing "**".
ENTRY = re.compile(r"^\s*- \*\*(\d{4}-\d{2}-\d{2},[^*]*)")
#: A note added to an existing entry.
NOTE = re.compile(
    r"(?:^|[.;:!?)]\s+)again\b|\bagain\b[^.]{0,60}?\d{4}-\d{2}-\d{2}"
    r"|\bupdated?\s+\d{4}-\d{2}-\d{2}|\brepeated\b|\brecurred\b|\bseen again\b",
    re.IGNORECASE)
LESSON_FIX = re.compile(r"^Lesson-fix:[ \t]*none\s*-\s*(.+)$", re.MULTILINE | re.IGNORECASE)

ADDED_WITHOUT_FIX = (
    f"This commit adds a lesson to {LESSONS} (a new entry or a note added to one) "
    "but changes no hook, test, script or code. Build the fix in this commit: a "
    "check that refuses the mistake, with its test. If no check is possible, add "
    "the line 'Lesson-fix: none - <why no check is possible>'."
)
REMOVED = (
    f"This commit removes a lesson entry from {LESSONS}. Lessons stay on record. "
    "Mark a fixed one 'Status: fixed YYYY-MM-DD, enforced by <check>' and a "
    "canceled one 'Status: canceled YYYY-MM-DD' with the reason, and commit again."
)


def _sides(diff: str) -> tuple[list[str], list[str]]:
    """(added lines, removed lines) of a unified diff."""
    added, removed = [], []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def _headers(lines: list[str]) -> set[str]:
    found = set()
    for line in lines:
        m = ENTRY.match(line)
        if m:
            found.add(" ".join(m.group(1).split()).rstrip(" ."))
    return found


def _new_text(added: list[str], removed: list[str]) -> list[str]:
    """Runs of words on the added side that the removed side lacks."""
    old, new = " ".join(removed).split(), " ".join(added).split()
    runs = []
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag in ("insert", "replace"):
            runs.append(" ".join(new[j1:j2]))
    return runs


def added_entries(diff: str) -> set[str]:
    added, removed = _sides(diff)
    return _headers(added) - _headers(removed)


def removed_entries(diff: str) -> set[str]:
    added, removed = _sides(diff)
    return _headers(removed) - _headers(added)


def added_notes(diff: str) -> list[str]:
    added, removed = _sides(diff)
    return [m.group(0) for run in _new_text(added, removed) for m in NOTE.finditer(run)]


def problems(message: str, staged: list[str], lessons_diff: str) -> list[str]:
    """What is wrong with this commit, in words; empty when it may go in."""
    if LESSONS not in staged:
        return []
    if removed_entries(lessons_diff):
        return [REMOVED]
    if not (added_entries(lessons_diff) or added_notes(lessons_diff)):
        return []
    if any(FIX.search(p) for p in staged if p != LESSONS):
        return []
    line = LESSON_FIX.search(message)
    if line is not None and len(line.group(1).strip()) >= 10:
        return []
    return [ADDED_WITHOUT_FIX]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: check_lesson_commit.py <commit message file>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        message = "\n".join(l for l in f.read().splitlines() if not l.startswith("#"))
    staged = _git("diff", "--cached", "--name-only").splitlines()
    diff = _git("diff", "--cached", "-U0", "--", LESSONS) if LESSONS in staged else ""
    found = problems(message, staged, diff)
    for problem in found:
        print(f"commit refused: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
