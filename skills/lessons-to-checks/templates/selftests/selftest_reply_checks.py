"""Self-test for reply_checks.py. Run with any Python 3.9+; every line says
"ok", and the last line is "ok" when all cases pass (exit 0).

The hook gets its input as Claude Code sends it, raw UTF-8 bytes, and one
check runs it behind a strict cp1252 console, as on Windows (hook_io.py).
Special characters are built with chr(), so this file holds none itself."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ beside the templates
from hook_io import behind_cp1252, run_hook

HOOK = Path(__file__).resolve().parent.parent / "reply_checks.py"
LQ, RQ = chr(0x201C), chr(0x201D)  # cp1252 cannot decode the UTF-8 bytes of RQ
CURLY_QUOTED = f"The guide{chr(0x2019)}s example reads {LQ}you decided to skip it{RQ}."


def transcript(folder, reply, tool_inputs=()):
    """A transcript of one turn: the person's message, tool calls with their
    results, then the reply."""
    path = os.path.join(folder, "transcript.jsonl")
    lines = [
        {"type": "user", "message": {"content": "an earlier question"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "It is 09:00."}]}},
        {"type": "user", "message": {"content": "what time is it, and is the job done?"}},
    ]
    for tool_input in tool_inputs:
        lines.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": tool_input}]}})
        lines.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "done"}]}})
    lines.append({"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}})
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def run(event, log):
    out = run_hook(HOOK, event, REPLY_CHECKS_LOG=log)
    return json.loads(out.stdout) if out.stdout.strip() else None


CASES = [
    # (description, reply, tool inputs this turn, second attempt?, stopped?)
    ("a current time with no clock read", "It is 14:05 now and the job is done.", [], False, True),
    ("the same, with the clock read this turn", "It is 14:05 now and the job is done.",
     [{"command": "date +%H:%M"}], False, False),
    ("the same, as the second attempt", "It is 14:05 now and the job is done.", [], True, False),
    ("a schedule time is not the current time", "The job runs at 14:05 each day.", [], False, False),
    ("a decision attributed to the person", "You decided to skip the slow tests.", [], False, True),
    ("the same words quoted from a document", 'The guide\'s example reads "you decided to skip it".',
     [], False, False),
    ("the same words in a block quote", "> You decided to skip the slow tests.", [], False, False),
    ("an ordinary reply", "The job finished and wrote 120 rows.", [], False, False),
]


def main():
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "reply_checks.log")
        for name, reply, tools, second, stopped in CASES:
            event = {"transcript_path": transcript(tmp, reply, tools), "stop_hook_active": second}
            result = run(event, log)
            got = bool(result) and result.get("decision") == "block"
            ok = got == stopped
            bad += not ok
            print("ok  " if ok else "BAD ", f"stopped={got!s:5} {name}")
        # The earlier turn's "It is 09:00." is not part of this reply.
        result = run({"transcript_path": transcript(tmp, "The job is done.")}, log)
        ok = result is None
        bad += not ok
        print("ok  " if ok else "BAD ", "only this turn's reply is read")
        # last_assistant_message is used when Claude Code gives it.
        result = run({"last_assistant_message": "As of 08:30 the queue is empty."}, log)
        ok = bool(result) and "clock" in result["reason"]
        bad += not ok
        print("ok  " if ok else "BAD ", "last_assistant_message is checked; the reason says what to verify")
        # Words in curly quotes are left out, as Claude Code sends them.
        result = run({"last_assistant_message": CURLY_QUOTED}, log)
        ok = result is None
        bad += not ok
        print("ok  " if ok else "BAD ", "words in curly quotes, sent as UTF-8, do not stop the reply")
        # Every run is logged, the second attempt marked.
        lines = Path(log).read_text(encoding="utf-8").splitlines()
        ok = (len(lines) == len(CASES) + 3
              and any("second attempt" in l for l in lines)
              and any("current time stated" in l for l in lines))
        bad += not ok
        print("ok  " if ok else "BAD ", f"log has one line per run ({len(lines)} lines)")
        # Behind a strict cp1252 console the hook still reads UTF-8.
        written = behind_cp1252(HOOK, {"last_assistant_message": "You decided to skip it. "
                                       + CURLY_QUOTED}, REPLY_CHECKS_LOG=log)
        ok = '"block"' in written and "decision attributed" in written
        bad += not ok
        print("ok  " if ok else "BAD ", "behind a cp1252 console a reply with curly quotes is read")
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
