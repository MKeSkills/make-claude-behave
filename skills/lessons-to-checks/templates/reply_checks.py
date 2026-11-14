"""Stop hook: check a reply before the person reads it.

Each entry in CHECKS is one lesson about how replies are written: a pattern
to look for in the reply and what Claude must do when it is found. When a
check matches, the reply is stopped once and Claude is told what to verify.
Claude then confirms or rewrites. Claude Code marks that second attempt with
`stop_hook_active`, and this hook lets it through, so it can never loop.

Optional keys of a check:

- `unless`: a pattern; the check does not fire when the reply also matches
  it (a proposal that names its source).
- `unless_tools`: a pattern; the check does not fire when one of this turn's
  tool calls matches it (the clock was read).

Quoted text (double quotes, block quotes, code) is left out before matching,
so wording quoted from someone else does not set a check off.

Every run is logged (time, milliseconds, checks fired) so each check's cost
can be judged at the periodic audit. A check that fires on more than about 1%
of replies, or mostly on ordinary work, is narrowed or dropped.

Register it (in .claude/settings.json of the project):

    "Stop": [
      {"hooks": [{"type": "command",
                  "command": "python \\"${CLAUDE_PROJECT_DIR}/.claude/hooks/reply_checks.py\\""}]}
    ]

Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime

CHECKS = [
    {
        # Lesson: a reply stated the current time without reading the clock.
        "name": "current time stated with no clock read",
        "pattern": re.compile(
            r"\b(?:it\s+is|it's|now|as\s+of)\s+(?:now\s+)?\d{1,2}:\d{2}\b", re.I),
        "unless_tools": re.compile(r"Get-Date|\bdate\b|datetime\.now|time\.localtime", re.I),
        "ask": "Read the clock in this turn before stating the current time, "
               "or remove the time.",
    },
    {
        # Lesson: a reply said the person decided something they never did.
        "name": "decision attributed to the person",
        "pattern": re.compile(
            r"\byou\s+(?:chose|decided|agreed|asked\s+me\s+to)\b|\bas\s+you\s+decided\b"
            r"|\bper\s+your\s+(?:decision|instruction)\b", re.I),
        "ask": "Find the person's own words for this decision and quote them, "
               "or say it was your choice for them to reverse.",
    },
]

TAIL_BYTES = 4 * 1024 * 1024


def log_path() -> str:
    """The log file: REPLY_CHECKS_LOG if set, else in the project's
    .claude/logs folder, else in a logs folder beside this script."""
    if os.environ.get("REPLY_CHECKS_LOG"):
        return os.environ["REPLY_CHECKS_LOG"]
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    base = os.path.join(project, ".claude") if project else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "logs", "reply_checks.log")


def read_turn(transcript_path: str) -> dict:
    """This turn's reply text and the inputs of its tool calls, read back
    from the transcript to the person's last message."""
    with open(transcript_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        lines = f.read().decode("utf-8", errors="replace").splitlines()
    texts: list[str] = []
    tools: list[str] = []
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "user":
            # A tool result is a "user" entry too; the person's message has text.
            if isinstance(content, str) or (isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "text" for b in content)):
                break
            continue
        if entry.get("type") == "assistant" and isinstance(content, list):
            texts[:0] = [b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text"]
            tools[:0] = [json.dumps(b.get("input") or {}) for b in content
                         if isinstance(b, dict) and b.get("type") == "tool_use"]
    return {"text": "\n".join(texts), "tools": "\n".join(tools)}


def outside_quotes(text: str) -> str:
    """The reply without code, block quotes and double-quoted spans."""
    text = re.sub(r"```.*?```|`[^`\n]+`", " ", text, flags=re.S)
    text = re.sub(r"(?m)^\s*>.*$", " ", text)
    return re.sub(r"\"[^\"\n]*\"|\u201c[^\u201d\n]*\u201d", " ", text)


def findings(text: str, tools: str = "") -> list[tuple[str, list[str], str]]:
    """(check name, matching phrases, what to do) for each check that fires."""
    prose = outside_quotes(text)
    out = []
    for check in CHECKS:
        found = sorted({m.group(0) for m in check["pattern"].finditer(prose)})
        if not found:
            continue
        if check.get("unless") is not None and check["unless"].search(text):
            continue
        if check.get("unless_tools") is not None and check["unless_tools"].search(tools):
            continue
        out.append((check["name"], found[:5], check["ask"]))
    return out


def log(started: float, fired: list[str], note: str = "") -> None:
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t"
                    f"{(time.perf_counter() - started) * 1000:.0f} ms\t"
                    f"{','.join(fired) or '-'}\t{note}\n")
    except OSError:
        pass


def main() -> None:
    started = time.perf_counter()
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    if event.get("stop_hook_active"):
        log(started, [], "second attempt, let through")
        return
    turn = {"text": "", "tools": ""}
    path = event.get("transcript_path") or ""
    if path:
        try:
            turn = read_turn(path)
        except OSError:
            pass
    text = event.get("last_assistant_message") or turn["text"]
    if not text:
        log(started, [], "no reply text")
        return
    try:
        found = findings(text, turn["tools"])
    except Exception:  # noqa: BLE001 - a fault in a check never blocks a reply
        log(started, [], "error")
        return
    log(started, [name for name, _, _ in found])
    if not found:
        return
    reason = "Reply checks, before this reply goes out:\n"
    for name, phrases, ask in found:
        reason += f"- {name}: {', '.join(repr(p) for p in phrases)}. {ask}\n"
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
