"""Self-test for guard_shell_habits.py. Run with any Python 3.9+; every line
says "ok", and the last line is "ok" when all cases pass (exit 0)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "guard_shell_habits.py"

CASES = [
    # (tool, command, refused?)
    ("Bash", "TZ=America/New_York date", True),
    ("Bash", "export TZ=Europe/Paris; date", True),
    ("PowerShell", "bash -c 'TZ=Asia/Tokyo date'", True),
    ("Bash", "TZ=UTC date", False),
    ("Bash", "echo the TZ variable is unset", False),
    ("Bash", "sed -i 's/old/new/' notes.txt", True),
    ("Bash", "sed --in-place 's/old/new/' notes.txt", True),
    ("Bash", "sed 's/old/new/' notes.txt > out.txt", False),
    ("Read", "TZ=America/New_York date", False),  # not a shell tool
]


def run(tool, command, log):
    event = {"tool_name": tool, "tool_input": {"command": command}, "cwd": os.getcwd()}
    env = dict(os.environ, SHELL_GUARD_LOG=log, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, env=env)


def main():
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "guard.log")
        for tool, command, refused in CASES:
            out = run(tool, command, log)
            decision = None
            if out.stdout.strip():
                decision = json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"]
            got = decision == "deny"
            ok = got == refused and out.returncode == 0
            bad += not ok
            print("ok  " if ok else "BAD ", f"refused={got!s:5} {tool}: {command}")
        # The reason says what to do instead.
        reason = json.loads(run("Bash", "TZ=America/New_York date", log).stdout)[
            "hookSpecificOutput"]["permissionDecisionReason"]
        ok = "zoneinfo" in reason and "named time zone" in reason
        bad += not ok
        print("ok  " if ok else "BAD ", "the refusal names the habit and what to do instead")
        # Every shell call is logged with its outcome.
        lines = Path(log).read_text(encoding="utf-8").splitlines()
        ok = (len(lines) == len(CASES) and any("\tdeny\t" in l for l in lines)
              and any("\tpass\t" in l for l in lines))
        bad += not ok
        print("ok  " if ok else "BAD ", f"log has one line per shell call ({len(lines)} lines)")
        # Malformed input never blocks.
        out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                             capture_output=True, text=True)
        ok = out.returncode == 0 and not out.stdout.strip()
        bad += not ok
        print("ok  " if ok else "BAD ", "unreadable input lets the call through")
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
