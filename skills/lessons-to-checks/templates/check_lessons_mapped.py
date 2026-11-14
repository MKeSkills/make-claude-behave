"""Every lesson is listed under a task procedure, and every listed line names a lesson.

Each procedure file (one Markdown file per kind of task) ends with a section
"## Lessons that apply here": one line per lesson that applies to the task,
opening with the lesson's date and short name in bold, exactly as the
lesson's own first line gives them:

    - **2025-01-14, a script stated the wrong time zone.** What to do
      instead. Check: the shell-habit guard.

A session reads that section before following the procedure, so a lesson
listed nowhere is never read when it matters. This check prints:

- "ok" when every lesson is listed somewhere and every line names a lesson
  that exists; exit 0;
- "MISSING: <date, name>" for each lesson listed nowhere,
  "UNKNOWN: <procedure>: <date, name>" for each line naming no lesson (a typo,
  or a lesson renamed in one place only), and
  "NO SECTION: <procedure>" for a procedure without the section; exit 1.

Saves tokens and time: a session reads the few lines under a task's
procedure instead of the whole lessons file, and this check keeps that
short list complete. A lesson listed nowhere is missed when its task comes
up, and its mistake costs another round to make, diagnose and fix. Example:
a new lesson about time zones, listed under no procedure, makes this check
print "MISSING: 2025-01-14, a script stated the wrong time zone".

Names are compared with whitespace collapsed and a final period dropped, so
a name wrapped over two lines still matches.

Usage:
    python check_lessons_mapped.py --lessons docs/lessons.md --procedures docs/procedures

It also works as a pytest test: `test_every_lesson_is_mapped` reads the paths
from the LESSONS_FILE and PROCEDURES_DIR environment variables, or the
defaults below. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DEFAULT_LESSONS = os.environ.get("LESSONS_FILE", "docs/lessons.md")
DEFAULT_PROCEDURES = os.environ.get("PROCEDURES_DIR", "docs/procedures")
HEADING = "## Lessons that apply here"

#: A lesson entry opens "- **YYYY-MM-DD, short name.**"; the name may wrap.
ENTRY = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2}, .*?)\*\*", re.MULTILINE | re.DOTALL)
#: A line of a "Lessons that apply here" section opens the same way.
LINE = re.compile(r"^- \*\*(.*?)\*\*", re.MULTILINE | re.DOTALL)


def key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(".")


def lesson_names(text: str) -> list[str]:
    return [key(m.group(1)) for m in ENTRY.finditer(text)]


def section(text: str) -> str | None:
    """The "Lessons that apply here" section, up to the next heading of its
    level or above, or None when the procedure has none."""
    lines = text.splitlines()
    try:
        start = lines.index(HEADING)
    except ValueError:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{1,2} ", lines[i]):
            end = i
            break
    return "\n".join(lines[start + 1:end])


def placed_names(text: str) -> list[str]:
    body = section(text)
    return [] if body is None else [key(m.group(1)) for m in LINE.finditer(body)]


def problems(lessons_text: str, procedures: dict[str, str]) -> list[str]:
    lessons = lesson_names(lessons_text)
    found = []
    starts = re.findall(r"^- \*\*\d{4}-\d{2}-\d{2}, ", lessons_text, re.MULTILINE)
    if len(starts) != len(lessons):
        found.append(f"UNREADABLE: {len(starts)} entries start, {len(lessons)} were read")
    if len(lessons) != len(set(lessons)):
        found.append("DUPLICATE: two lessons share a date and name")
    placed = {name for text in procedures.values() for name in placed_names(text)}
    for name in lessons:
        if name not in placed:
            found.append(f"MISSING: {name}")
    known = set(lessons)
    for proc, text in sorted(procedures.items()):
        if section(text) is None:
            found.append(f"NO SECTION: {proc}")
            continue
        for name in placed_names(text):
            if name not in known:
                found.append(f"UNKNOWN: {proc}: {name}")
    return found


def read_procedures(folder: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.md"))}


def run(lessons: Path, procedures: Path) -> list[str]:
    return problems(lessons.read_text(encoding="utf-8"), read_procedures(procedures))


def test_every_lesson_is_mapped():
    """For pytest."""
    found = run(Path(DEFAULT_LESSONS), Path(DEFAULT_PROCEDURES))
    assert found == [], "\n".join(found)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lessons", default=DEFAULT_LESSONS)
    parser.add_argument("--procedures", default=DEFAULT_PROCEDURES)
    args = parser.parse_args(argv)
    found = run(Path(args.lessons), Path(args.procedures))
    for line in found:
        print(line)
    if found:
        return 1
    print("ok (every lesson is listed under a procedure)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
