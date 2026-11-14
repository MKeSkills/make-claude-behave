"""PreToolUse hook: refuse shell commands that went wrong before.

Each entry in HABITS is one lesson turned into a check: a name, a regular
expression matched against the command text, and the reason shown when it
matches. The reason says what to do instead, so the next attempt can succeed.
The hook refuses outright ("deny"); it never asks the person, so it adds no
prompts to routine work.

Saves tokens and time: a command that went wrong before costs the failed
attempt, a round to find out what went wrong, and the retry. A wrong answer
that reaches a reply also costs the person the time to spot it and correct
it. The hook refuses the command before it runs and names the right one,
so the next attempt is the right one. Example: `TZ=America/New_York date`
is refused with a pointer to a clock that honors the zone, before the UTC
time it would print is taken for local time.

Add a habit by adding an entry, plus two cases to the self-test (one command
that must be refused, one similar command that must pass). Then register the
hook in a settings file and see it refuse a harmless command that matches it.

Register it (in .claude/settings.json of the project):

    "PreToolUse": [
      {"matcher": "Bash|PowerShell",
       "hooks": [{"type": "command",
                  "command": "python \\"${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_shell_habits.py\\""}]}
    ]

Every call is logged (time, outcome, the habits that fired) so the firing
rate can be judged at the periodic audit. A fault inside the hook lets the
command through: a broken check must never stop work.

Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

#: (name, pattern, what to do instead). Patterns are matched against the
#: whole command text. Keep each one narrow: a check that refuses ordinary
#: work gets switched off.
HABITS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "named time zone in TZ=",
        # TZ=America/New_York date  or  export TZ=Europe/Paris
        re.compile(r"(?:^|[\s;&|('\"])(?:export\s+)?TZ=['\"]?[A-Za-z]+/[A-Za-z_]+"),
        "This shell has no time-zone database, so a named zone in TZ= is "
        "ignored and the time printed is UTC (lesson: a script stated the "
        "wrong time zone). Read the local time with a tool that honors the "
        "zone, such as Python's zoneinfo with the tzdata package installed.",
    ),
    (
        "sed -i",
        re.compile(r"(?:^|[\s;&|(])sed\s+(?:-[A-Za-z]*i|--in-place)"),
        "sed -i rewrites the whole file and can change its line endings. "
        "Edit the file with the editor tool instead.",
    ),
]

TOOLS = ("Bash", "PowerShell")


def log_path() -> str:
    """The log file: SHELL_GUARD_LOG if set, else in the project's
    .claude/logs folder, else in a logs folder beside this script."""
    if os.environ.get("SHELL_GUARD_LOG"):
        return os.environ["SHELL_GUARD_LOG"]
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    base = os.path.join(project, ".claude") if project else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "logs", "guard_shell_habits.log")


def reasons(command: str) -> list[tuple[str, str]]:
    """(name, reason) for each habit the command shows."""
    return [(name, why) for name, pattern, why in HABITS if pattern.search(command)]


def log(outcome: str, names: list[str]) -> None:
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{outcome}\t{','.join(names) or '-'}\n")
    except OSError:
        pass


def read_event() -> object:
    """The event, read as UTF-8 bytes whatever the console's code page. Read
    as text on Windows, it would be decoded as cp1252, and every em dash and
    curly quote would arrive as other characters."""
    return json.loads(sys.stdin.buffer.read().decode("utf-8"))


def answer(payload: dict) -> None:
    """Write the answer to stdout as UTF-8 whatever the console's code page."""
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def main() -> None:
    try:
        event = read_event()
    except ValueError:
        return
    if event.get("tool_name") not in TOOLS:
        return
    command = (event.get("tool_input") or {}).get("command") or ""
    try:
        found = reasons(command)
    except Exception:  # noqa: BLE001 - a fault in the check never blocks work
        log("error", [])
        return
    log("deny" if found else "pass", [name for name, _ in found])
    if found:
        answer({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": " ".join(
                    f"Refused ({name}): {why}" for name, why in found),
            }
        })


if __name__ == "__main__":
    main()
