"""Self-test for guard_agent_prompts.py. Run with any Python 3.9+; every line
says "ok", and the last line is "ok" when all cases pass (exit 0)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "guard_agent_prompts.py"

NO_FULL = " Run only the targeted tests for what you change; no full run."
OWN = r" Keep scratch files in C:\tmp\scratchpad\fix-login\ only."

CASES = [
    # (tool, extra tool_input, prompt, names of the checks that must refuse it)
    # 1. Full runs.
    ("Agent", {}, "Build the export button and add its tests.", ["full runs"]),
    ("Agent", {}, "Fix the rounding bug in invoices.py.", ["full runs"]),
    ("Agent", {}, "Change the function parse_date so it accepts ISO dates.", ["full runs"]),
    ("Task", {}, "Implement the retry loop.", ["full runs"]),
    ("Agent", {}, "Build the export button." + NO_FULL, []),
    ("Agent", {}, "Implement the retry loop, then run the whole suite once at the end.", []),
    ("Agent", {}, "Do not build anything. List the files that import parse_date.", []),
    ("Agent", {}, "The build already ran on the server; read its log and summarize it.", []),
    ("Agent", {"subagent_type": "Explore"}, "Find where the fix for issue 12 lives.", []),
    ("Agent", {}, "Review the diff with read-only access; say what a fix would need.", []),
    ("Agent", {}, "Implement the importer. The config file is read-only.", ["full runs"]),
    ("Agent", {}, "Summarize the release notes for the team.", []),
    ("Agent", {}, "Read the log in /tmp/build/ and the fix-login branch notes.", []),
    # 2. Own scratch folder.
    ("Agent", {}, r"Use the session scratchpad at C:\tmp\scratchpad for notes.", ["own scratch folder"]),
    ("Agent", {}, "Put helper scripts in the scratch folder.", ["own scratch folder"]),
    ("Agent", {}, r"Write the helper to C:\tmp\scratchpad\mutate.py and run it.", ["own scratch folder"]),
    ("Agent", {}, "Write the helper to /tmp/scratch/mutate.py and run it.", ["own scratch folder"]),
    ("Agent", {}, r"Your scratch folder is C:\tmp\scratchpad\fix-login (yours alone).", []),
    ("Agent", {}, "Keep helpers in /tmp/scratchpad/fix-login/mutate.py.", []),
    ("Agent", {}, "Do not use the scratchpad; write nothing to disk.", []),
    ("Agent", {}, "Write the parser from scratch, in plain Python." + NO_FULL, []),
    # 3. Agent starting agents.
    ("Agent", {}, "When done, launch an independent reviewer on the diff.", ["agent starting agents"]),
    ("Agent", {}, "Spawn two sub-agents to search the logs.", ["agent starting agents"]),
    ("Agent", {}, "Then kick off a code review of your change.", ["agent starting agents"]),
    ("Agent", {}, "Do not launch a reviewer; hand back, and the main session starts it.", []),
    ("Agent", {}, "Never spawn agents. Summarize the log.", []),
    ("Agent", {}, "Start the agent's work by reading the log.", []),
    # Several at once, and tools the hook does not watch.
    ("Agent", {}, "Build it; put scripts in the scratchpad; then launch a reviewer.",
     ["full runs", "own scratch folder", "agent starting agents"]),
    ("Bash", {}, "Build it.", []),
]


def run(tool, extra, prompt, log):
    tool_input = dict(extra, prompt=prompt)
    event = {"tool_name": tool, "tool_input": tool_input, "cwd": os.getcwd()}
    env = dict(os.environ, AGENT_GUARD_LOG=log, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, env=env)


def refused_by(out):
    if not out.stdout.strip():
        return []
    reason = json.loads(out.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    return [name for name in ("full runs", "own scratch folder", "agent starting agents")
            if f"Refused ({name})" in reason]


def main():
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "guard.log")
        watched = 0
        for tool, extra, prompt, expected in CASES:
            out = run(tool, extra, prompt, log)
            watched += tool in ("Agent", "Task")
            got = refused_by(out)
            ok = got == expected and out.returncode == 0
            bad += not ok
            print("ok  " if ok else "BAD ", f"refused={got} {tool} {extra or ''}: {prompt}")
        # The refusal says which line to add.
        out = run("Agent", {}, "Build the export button.", log)
        watched += 1
        decision = json.loads(out.stdout or "{}").get("hookSpecificOutput", {})
        ok = ("no full run" in decision.get("permissionDecisionReason", "")
              and decision.get("permissionDecision") == "deny")
        bad += not ok
        print("ok  " if ok else "BAD ", "the refusal is a deny and names the line to add")
        # A fault inside the check lets the call through, and is logged.
        out = run("Agent", {}, 12345, log)
        watched += 1
        ok = out.returncode == 0 and not out.stdout.strip()
        bad += not ok
        print("ok  " if ok else "BAD ", "a fault inside the check lets the call through")
        # Every watched call is logged with its outcome.
        lines = Path(log).read_text(encoding="utf-8").splitlines()
        ok = (len(lines) == watched and any("\tdeny\t" in l for l in lines)
              and any("\tpass\t" in l for l in lines) and lines[-1].split("\t")[1] == "error")
        bad += not ok
        print("ok  " if ok else "BAD ", f"log has one line per watched call ({len(lines)} of {watched})")
        # Unreadable input never blocks.
        out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                             capture_output=True, text=True,
                             env=dict(os.environ, AGENT_GUARD_LOG=log))
        ok = out.returncode == 0 and not out.stdout.strip()
        bad += not ok
        print("ok  " if ok else "BAD ", "unreadable input lets the call through")
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
