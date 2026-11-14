"""PreToolUse hook: refuse an agent prompt that lacks a line its work needs.

An agent knows only what its prompt says. Each entry in CHECKS is one lesson
about agent prompts turned into a check: a name, when it applies, what the
prompt must carry, and the reason shown when it is missing. The reason says
which line to add, so the next attempt can succeed. The hook refuses outright
("deny"); it never asks the person, so it adds no prompts to routine work.

The checks in this template:

1. "full runs". A prompt that asks for code to be built or changed must say
   whether the agent runs the full test suite (lesson: every builder agent
   ran the full suite, and only the run on the combined tree counted). Any
   mention of the full suite or a full run counts, either way round: "no
   full run" and "run the full suite once at the end" both pass. Read-only
   prompts and read-only agent types (READ_ONLY_TYPES) build nothing and
   are left alone.
2. "own scratch folder". A prompt that names the shared scratch folder must
   give the agent a subfolder of its own (lesson: parallel agents wrote
   helper scripts with common names, such as `mutate.py`, to one scratch
   folder and replaced each other's). Refused: a prompt that mentions the
   scratch folder with no subfolder path anywhere, or that names a file
   directly in it (`scratchpad/mutate.py`). Passes: `scratchpad/fix-login/`
   or `scratchpad\\fix-login`.
3. "agent starting agents". A prompt must not ask the agent to start
   another agent (lesson: a background agent told to launch an independent
   review could not; agents started from another agent cannot start agents,
   and no permission prompt reaches the person from one). The main session
   starts every agent and review itself.

A mention that is negated ("do not build", "never launch a reviewer") or
reported as past ("the build already ran") is not the work asked for, and
does not count.

Add a check by adding an entry to CHECKS, plus two cases to the self-test
(one prompt that must be refused, one similar prompt that must pass). Then
register the hook in a settings file and see it refuse a harmless prompt
that matches it.

Register it (in .claude/settings.json of the project):

    "PreToolUse": [
      {"matcher": "Agent|Task",
       "hooks": [{"type": "command",
                  "command": "python \\"${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_agent_prompts.py\\""}]}
    ]

Every call is logged (time, outcome, the checks that fired) so the firing
rate can be judged at the periodic audit. A fault inside the hook lets the
call through: a broken check must never stop work.

Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from typing import Callable

TOOLS = ("Agent", "Task")

#: Agent types that only search, read or plan: they build nothing, so the
#: "full runs" check is left out for them. Adjust to the types you use.
READ_ONLY_TYPES = {"Explore", "Plan", "claude-code-guide", "statusline-setup"}

#: A mention that is negated just before it ("do not", "never", up to two
#: words in between) or reported as past just after it ("already ran").
NEGATED_BEFORE = re.compile(
    r"\b(?:do\s+not|don't|never|not|no|without|nor|cannot|can't|must\s+not)\s+(?:\w+\s+){0,2}$",
    re.IGNORECASE)
PAST_AFTER = re.compile(
    r"^\s+(?:already\s+|has\s+|had\s+|was\s+|were\s+)?(?:found|ran|run|reported|said|"
    r"passed|done|finished|failed|came\s+back)\b", re.IGNORECASE)


def is_live(match: re.Match[str], prompt: str) -> bool:
    """True when this mention is neither negated nor reported as past."""
    before = prompt[max(0, match.start() - 30):match.start()]
    after = prompt[match.end():match.end() + 30]
    return not (NEGATED_BEFORE.search(before) or PAST_AFTER.match(after))


def live(pattern: re.Pattern[str], prompt: str) -> re.Match[str] | None:
    """The first match of `pattern` that is neither negated nor reported as
    past, or None."""
    for match in pattern.finditer(prompt):
        if is_live(match, prompt):
            return match
    return None


# 1. Full runs ---------------------------------------------------------------

#: Work that changes code. Keep it narrow: a check that refuses ordinary
#: prompts gets switched off. A word inside a name or path ("fix-login",
#: "src/build/") does not count.
BUILD = re.compile(
    r"(?<![\w\\/.-])(?:build|implement|fix|refactor)(?![\w\\/-])"
    r"|\b(?:change|modify|edit|update|rewrite)\s+(?:the\s+|this\s+|that\s+|its\s+|each\s+)?"
    r"(?:code|function|script|module|class|tests?|hook|program)s?\b",
    re.IGNORECASE)
#: The agent itself works read-only (a review or a search): "read-only
#: access", "a read-only review", "work read-only", "the diff, read-only,
#: against the rules". A file called read-only ("the config is read-only")
#: does not count.
READ_ONLY = re.compile(
    r"\bread-only\s+(?:access|review|reviewer|agent|search|audit)\b"
    r"|\b(?:work|works|working|stay|stays|remain|remains)\s+read-only\b"
    r"|,\s*read-only\s*,",
    re.IGNORECASE)
FULL_RUN = re.compile(
    r"\b(?:full|whole|entire)\s+(?:test\s+)?(?:suite|run|test\s+run)s?\b", re.IGNORECASE)


def full_run_problem(prompt: str, tool_input: dict) -> str | None:
    if tool_input.get("subagent_type") in READ_ONLY_TYPES or READ_ONLY.search(prompt):
        return None
    match = live(BUILD, prompt)
    if match is None or FULL_RUN.search(prompt):
        return None
    return match.group(0)


FULL_RUN_REASON = (
    "this prompt asks for code to be built or changed ({detail!r}) but does "
    "not say whether the agent runs the full test suite. Builder agents that "
    "each ran the whole suite repeated a run only the combined tree needed "
    "(lesson: every builder agent ran the full suite). Add a line such as: "
    "\"Run only the targeted and mutation tests for what you change; no full "
    "run (the full suite runs once per batch, on the combined tree).\" Or, "
    "for the agent that runs the batch's one full run, say so."
)


# 2. Own scratch folder ------------------------------------------------------

#: The scratch folder named in a path, with what follows it. `rest` is the
#: next path part; `sep` is set when a separator follows that part, which
#: makes it a folder.
SCRATCH_PATH = re.compile(
    r"(?:scratchpad|(?<=[\\/])scratch)(?![\w-])"
    r"(?P<rest>[\\/][^\s\\/'\"`),;:]+(?P<sep>[\\/])?)?",
    re.IGNORECASE)
#: The scratch folder named in words. "from scratch" does not count.
SCRATCH_WORDS = re.compile(r"\bscratch[ -](?:folder|directory|dir)\b", re.IGNORECASE)
FILE_NAME = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def scratch_problem(prompt: str, tool_input: dict) -> str | None:
    bare = False
    own_folder = False
    for match in SCRATCH_PATH.finditer(prompt):
        if not is_live(match, prompt):
            continue
        rest = match.group("rest")
        if not rest:
            bare = True
            continue
        name = rest[1:]
        if match.group("sep") is None and FILE_NAME.search(name):
            return f"a file directly in it: {match.group(0)}"
        own_folder = True
    if live(SCRATCH_WORDS, prompt):
        bare = True
    if bare and not own_folder:
        return "it is mentioned, but no subfolder is named"
    return None


SCRATCH_REASON = (
    "this prompt names the shared scratch folder without giving the agent a "
    "subfolder of its own ({detail}). Parallel agents have overwritten each "
    "other's scratch files there (lesson: agents overwrote each other's "
    "scratch files). Name a subfolder for this agent, after its task, and "
    "tell it to keep every scratch file there, for example "
    "<scratch folder>/<task-name>/."
)


# 3. Agent starting agents ---------------------------------------------------

START_AGENT = re.compile(
    r"\b(?:launch|spawn|start|kick\s+off|fire\s+off)\s+"
    r"(?:(?:an?|the|your\s+own|one|two|three|several|parallel|separate|independent|new|fresh"
    r"|another|other|read-only|code|design)\s+){0,4}"
    r"(?:sub-?agents?|agents?|reviewers?)\b(?!['\u2019])"
    r"|\b(?:launch|spawn|kick\s+off)\s+(?:(?:an?|the|your\s+own|separate|independent|new|code"
    r"|design)\s+){0,3}reviews?\b",
    re.IGNORECASE)


def start_problem(prompt: str, tool_input: dict) -> str | None:
    match = live(START_AGENT, prompt)
    return match.group(0) if match else None


START_REASON = (
    "this prompt asks the agent to start another agent ({detail!r}). An "
    "agent started from another agent cannot start agents, and no permission "
    "prompt reaches the person from one (lesson: a background agent could "
    "not launch the review it was told to). Have the agent stop and hand "
    "back; the main session starts the review or agent itself."
)


#: (name, problem(prompt, tool_input) -> detail or None, reason with {detail}).
CHECKS: list[tuple[str, Callable[[str, dict], str | None], str]] = [
    ("full runs", full_run_problem, FULL_RUN_REASON),
    ("own scratch folder", scratch_problem, SCRATCH_REASON),
    ("agent starting agents", start_problem, START_REASON),
]


def reasons(prompt: str, tool_input: dict) -> list[tuple[str, str]]:
    """(name, reason) for each check the prompt fails."""
    out = []
    for name, problem, why in CHECKS:
        detail = problem(prompt, tool_input)
        if detail:
            out.append((name, why.format(detail=detail)))
    return out


def log_path() -> str:
    """The log file: AGENT_GUARD_LOG if set, else in the project's
    .claude/logs folder, else in a logs folder beside this script."""
    if os.environ.get("AGENT_GUARD_LOG"):
        return os.environ["AGENT_GUARD_LOG"]
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    base = os.path.join(project, ".claude") if project else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "logs", "guard_agent_prompts.log")


def log(outcome: str, names: list[str]) -> None:
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{outcome}\t{','.join(names) or '-'}\n")
    except OSError:
        pass


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        log("error", [])
        return
    try:
        if event.get("tool_name") not in TOOLS:
            return
        tool_input = event.get("tool_input") or {}
        found = reasons(tool_input.get("prompt") or "", tool_input)
    except Exception:  # noqa: BLE001 - a fault in the check never blocks work
        log("error", [])
        return
    log("deny" if found else "pass", [name for name, _ in found])
    if found:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": " ".join(
                    f"Refused ({name}): {why}" for name, why in found),
            }
        }))


if __name__ == "__main__":
    main()
