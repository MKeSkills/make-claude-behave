"""Self-test for guard_writing_style.py. Run with any Python 3.9+; every line
says "ok", and the last line is "ok" when all cases pass (exit 0).

The hook gets its input the way Claude Code sends it: raw UTF-8 bytes, with
UTF-8 mode off and no PYTHONIOENCODING in its environment. One more check
runs the hook in this process behind a strict cp1252 console, as on Windows.

Special characters are built with chr(), so this file holds none itself."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ beside the templates
from hook_io import behind_cp1252, run_hook

HOOK = Path(__file__).resolve().parent.parent / "guard_writing_style.py"

EM = chr(0x2014)
EN = chr(0x2013)
LQ, RQ = chr(0x201C), chr(0x201D)
APOS = chr(0x2019)

PASSIVE_TEXT = ("The keys are stored on disk. The logs are kept for a year. "
                "The report was sent at noon. The team checks the backups.")
MOSTLY_ACTIVE = ("The keys are stored on disk. The logs are kept for a year. "
                 "The report was sent at noon. " + " ".join(
                     f"The team checks item {n} each day." for n in range(10)))
STEPS = ("Run in a terminal. Set to 5 by default. Read from the config file. "
         "Proceed to step 5. Open the page. Split into two files. Put in the folder. "
         "Embed in the page. Based on the log, the job ran.")
GET_PASSIVE = ("The file gets deleted. The keys get stored. The log got sent. "
               "The team reads it.")
FILLER = " ".join(f"The team checks item {n} each day." for n in range(56))
THREE_IN_LONG = ("Say what happens, not what fails. Name the doer, not the tool. "
                 "Use the name, not a pronoun. " + FILLER)
FOUR_IN_LONG = THREE_IN_LONG + " Write the date, not the weekday."
MIT = """MIT License

Copyright (c) 2026 Example

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

CASES = [
    # (name, text written to notes.md by Write, refused?)
    ("em dash", f"The guide covers setup {EM} and then the first run.", True),
    ("en dash used as a dash", f"The guide covers setup {EN} and then the first run.", True),
    ("en dash in a range", f"Read pages 10{EN}20 before the first run.", False),
    ("negative reassurance", "Rest assured, the draft stays in your outbox.", True),
    ("nothing is lost", "Close the window. Nothing is lost.", True),
    ("curly don't worry", f"You don{APOS}t need to worry about the cache.", True),
    ("simply", "Simply run the installer.", True),
    ("just downplaying", "Just click Save.", True),
    ("just as time", "The job starts just before noon.", False),
    ("tell word", "The sync is seamless.", True),
    ("leverage", "The tool will leverage the cache.", True),
    ("two contrasts in a short text", "Say what happens, not what fails. Name the doer, not the tool.",
     True),
    ("one contrast", "Say what happens, not what fails. Name the doer.", False),
    ("three contrasts in 59 sentences", THREE_IN_LONG, False),
    ("four contrasts in 60 sentences", FOUR_IN_LONG, True),
    ("passive share", PASSIVE_TEXT, True),
    ("passive under a quarter", MOSTLY_ACTIVE, False),
    ("passive with get", GET_PASSIVE, True),
    ("steps that start with a verb", STEPS, False),
    ("get started is not passive", "Get started here. Getting started takes a minute. "
     "To get started, open the page. The team reads it.", False),
    ("active text", "The hook reads the text. It lists each hit. Claude rewrites it.", False),
    ("fenced code skipped",
     f"The example:\n\n```\nRest assured {EM} it is seamless.\nIt was sent. It was kept. "
     "It was made.\n```\n\nThe hook reads the text.", False),
    ("tilde fence skipped", "Text.\n\n~~~\nSimply run it.\n~~~\n", False),
    ("unclosed fence skipped to the end", "Text.\n\n```\nSimply run it.\nIt is seamless.\n", False),
    ("text after a closed fence checked", "Text.\n\n```\ncode\n```\n\nSimply run it.\n", True),
    ("indented code skipped",
     "The example:\n\n    Simply run it.\n    It is seamless.\n\nThe hook reads the text.", False),
    ("indented text in a list checked", "- Step one.\n\n    Simply run it.\n", True),
    ("inline code skipped", "Type `simply run it` in the box.", False),
    ("URL skipped", "See https://example.com/seamless-robust-delve for details.", False),
    ("relative link target skipped", "See the [guide](docs/seamless-sync.md) for setup.", False),
    ("link with a title skipped", 'See the [guide](docs/seamless-sync.md "Seamless sync").', False),
    ("reference definition skipped", "See the [guide].\n\n[guide]: docs/seamless-sync.md\n", False),
    ("link text checked", "See the [seamless guide](docs/setup.md).", True),
    ("HTML tag skipped", '<img src="docs/seamless.png" alt="robust">\n\nThe hook reads it.', False),
    ("straight quotes skipped", 'The person wrote "rest assured, nothing is lost" in the note.',
     False),
    ("curly quotes skipped", f"The person wrote {LQ}rest assured, it is seamless{RQ} once.",
     False),
    ("quote across a wrapped line", 'The person wrote "rest assured,\nnothing is lost" once.',
     False),
    ("quotation holding quotations", 'The person wrote "avoid "silently" and "honestly" here" once.',
     False),
    ("curly quotation holding straight ones",
     f'The person wrote {LQ}avoid "silently" and "honestly" here{RQ} once.', False),
    ("text after a quotation checked", 'The person wrote "a note" once. It is seamless.', True),
    ("single quotes checked", "The person wrote 'it is seamless' once.", True),
    ("block quote skipped", "The person wrote:\n\n> Rest assured, nothing is lost.\n\nDone.",
     False),
    ("front matter skipped", "---\ndescription: a seamless guide\n---\n# Guide\n\nRead it.",
     False),
    ("front matter with CRLF skipped",
     "---\r\ndescription: a seamless guide\r\n---\r\n# Guide\r\n\r\nRead it.\r\n", False),
    ("html comment skipped", "<!-- simply a note -->\nThe hook reads it.", False),
    ("unclosed html comment skipped to the end", "The hook reads it.\n<!-- simply a note\nmore", False),
    ("license text in a document is checked", MIT, True),
]


def run(event, state, log, raw=None):
    return run_hook(HOOK, event, raw=raw, WRITING_STYLE_STATE=state, WRITING_STYLE_LOG=log)


def denied(out):
    if not out.stdout.strip():
        return None
    data = json.loads(out.stdout)["hookSpecificOutput"]
    return data["permissionDecisionReason"] if data["permissionDecision"] == "deny" else None


def write(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def load_guard():
    spec = importlib.util.spec_from_file_location("guard_writing_style", HOOK)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard


def main():
    bad = 0

    def check(ok, label):
        nonlocal bad
        bad += not ok
        print("ok  " if ok else "BAD ", label)

    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "guard.log")

        def state(name):
            return os.path.join(tmp, name + ".json")

        doc = os.path.join(tmp, "notes.md")
        for i, (name, text, refused) in enumerate(CASES):
            out = run(write(doc, text), state(f"case{i}"), log)
            got = denied(out) is not None
            check(got == refused and out.returncode == 0, f"refused={got!s:5} {name}")

        # The refusal names the check, the line and a fix, and quotes the
        # line with its em dash intact.
        why = denied(run(write(doc, "Line one.\nLine two.\nSimply run it.\n"), state("why"), log))
        check(bool(why) and "negative reassurance" in why and "line 3" in why and "Fix:" in why,
              "the refusal names the check, the line and a fix")
        why = denied(run(write(doc, f"Setup {EM} then run."), state("dash"), log))
        check(bool(why) and f"Setup {EM} then run." in why,
              "the refusal quotes the line as written, em dash included")

        # Refused once; the identical call sent again passes; a changed call is checked again.
        event = write(doc, "Rest assured, it works.")
        first = denied(run(event, state("once"), log))
        second = denied(run(event, state("once"), log))
        third = denied(run(write(doc, "Rest assured, it still works."), state("once"), log))
        check(first is not None and second is None and third is not None,
              "refused once, the same call again passes, a changed call is refused")

        # Only documentation files are checked; license files never are.
        out = run(write(os.path.join(tmp, "tool.py"), f"# setup {EM} seamless"), state("py"), log)
        check(denied(out) is None, "a .py file is not checked")
        out = run(write(os.path.join(tmp, "NOTES.TXT"), "Simply run it."), state("txt"), log)
        check(denied(out) is None, "a .txt file is not checked by default")
        out = run(write(os.path.join(tmp, "GUIDE.MD"), "Simply run it."), state("upper"), log)
        check(denied(out) is not None, "a .MD file is checked")
        for name in ("LICENSE", "LICENSE.md", "license.txt", "LICENCE.md"):
            out = run(write(os.path.join(tmp, name), MIT), state("license-" + name), log)
            check(denied(out) is None, f"the MIT license text in {name} is not checked")
        out = run({"tool_name": "Read", "tool_input": {"file_path": doc}}, state("read"), log)
        check(denied(out) is None, "a Read call is not checked")

        # Edit: only the new text counts, and the line is the file's line.
        existing = os.path.join(tmp, "guide.md")
        Path(existing).write_text("# Guide\n\nRest assured, it is seamless.\n\nOld line.\n",
                                  encoding="utf-8")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": existing, "old_string": "Old line.", "new_string": "The hook reads it."}}
        check(denied(run(edit, state("edit1"), log)) is None,
              "an Edit with clean new text passes, whatever the rest of the file says")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": existing, "old_string": "Rest assured, it is seamless.",
            "new_string": "The sync works."}}
        check(denied(run(edit, state("edit2"), log)) is None,
              "an Edit that removes bad text passes (the old text is not checked)")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": existing, "old_string": "Old line.", "new_string": "Simply run it."}}
        why = denied(run(edit, state("edit3"), log))
        check(bool(why) and "line 5" in why, "an Edit with bad new text is refused at its file line")
        multi = {"tool_name": "MultiEdit", "tool_input": {"file_path": existing, "edits": [
            {"old_string": "# Guide", "new_string": "# The guide"},
            {"old_string": "Old line.", "new_string": "The sync is robust."}]}}
        check(denied(run(multi, state("multi"), log)) is not None,
              "a MultiEdit with one bad edit is refused")
        multi = {"tool_name": "MultiEdit", "tool_input": {"file_path": existing, "edits": [
            {"old_string": "# Guide", "new_string": "# Guide\n\nIntro one.\nIntro two."},
            {"old_string": "Old line.", "new_string": "Simply run it."}]}}
        why = denied(run(multi, state("multi-lines"), log))
        check(bool(why) and "line 8" in why,
              "a MultiEdit names the line in the edited file, after earlier edits moved it")

        # Edit inside a fenced block or an HTML comment of the file.
        fenced = os.path.join(tmp, "fenced.md")
        Path(fenced).write_text("# Guide\n\n```\nold code\n```\n\n<!--\nold note\n-->\n\nText.\n",
                                encoding="utf-8")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": fenced, "old_string": "old code",
            "new_string": f"x = 1  # simply run it {EM} seamless"}}
        check(denied(run(edit, state("in-fence"), log)) is None,
              "an Edit inside a fenced block of the file is treated as code")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": fenced, "old_string": "old note", "new_string": "simply a seamless note"}}
        check(denied(run(edit, state("in-comment"), log)) is None,
              "an Edit inside an HTML comment of the file is treated as a comment")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": fenced, "old_string": "Text.", "new_string": "Simply run it."}}
        check(denied(run(edit, state("after-fence"), log)) is not None,
              "an Edit after the fence and the comment is checked")
        edit = {"tool_name": "Edit", "tool_input": {
            "file_path": fenced, "old_string": "old code\n```",
            "new_string": "new code\n```\n\nSimply run it."}}
        check(denied(run(edit, state("closes-fence"), log)) is not None,
              "an Edit that closes the fence and adds text has that text checked")

        # Every documentation call is logged as one JSON line, with what a
        # report needs to count refusals and unchanged resends per check.
        lines = [json.loads(l) for l in Path(log).read_text(encoding="utf-8").splitlines()]
        check({"deny", "pass", "pass-resent"} <= {e.get("outcome") for e in lines}
              and all("time" in e for e in lines),
              f"log has deny, pass and pass-resent JSON lines ({len(lines)} lines)")
        measure = os.path.join(tmp, "measure.log")
        long_passive = "The " + "very " * 20 + "old keys are stored on disk."
        event = write(doc, f"Line one.\nSimply run it.\n{long_passive} It was sent. It was kept.\n")
        for _ in range(2):
            run(event, state("measure"), measure)
        run(write(doc, "The hook reads the text."), state("measure"), measure)
        entries = [json.loads(l) for l in Path(measure).read_text(encoding="utf-8").splitlines()]
        deny, resent, clean = (entries + [{}, {}, {}])[:3]
        hits = deny.get("hits") or []
        simply = [h for h in hits if h.get("check") == "negative reassurance"]
        passive = [h for h in hits if h.get("check") == "passive voice"]
        check(deny.get("outcome") == "deny" and deny.get("tool") == "Write"
              and deny.get("file") == doc and len(deny.get("hash", "")) == 64
              and simply and simply[0]["line"] == 2 and simply[0]["text"] == "Simply"
              and passive and all(len(h["text"]) <= 80 for h in passive)
              and passive[0]["text"].startswith("The very"),
              "a refusal logs tool, file, hash and each hit's check, line and text (80 at most)")
        check(resent.get("outcome") == "pass-resent" and resent.get("hash") == deny.get("hash")
              and "negative reassurance" in resent.get("checks", []),
              "an unchanged resend logs the same hash")
        check(clean.get("outcome") == "pass" and clean.get("file") == doc and "hits" not in clean,
              "a clean pass logs a short line")

        # Malformed input and a fault let the call through.
        for raw in ("not json", "[1, 2]", '{"tool_name": "Write", "tool_input": 5}', ""):
            out = run(None, state("raw"), log, raw=raw)
            check(out.returncode == 0 and not out.stdout.strip(), f"malformed input passes: {raw!r}")
        blocker = os.path.join(tmp, "a-file")
        Path(blocker).write_text("x", encoding="utf-8")
        out = run(write(doc, "Simply run it."), os.path.join(blocker, "state.json"), log)
        check(out.returncode == 0 and not out.stdout.strip() and "let the call through" in out.stderr,
              "a fault inside the hook lets the call through")

        # Behind a strict cp1252 console the hook still reads and writes UTF-8.
        written = behind_cp1252(HOOK, write(doc, f"Setup {EM} then run."),
                                WRITING_STYLE_STATE=state("cp1252"), WRITING_STYLE_LOG=log)
        check(f"Setup {EM} then run." in written and '"deny"' in written,
              "behind a cp1252 console the em dash is read and quoted back as UTF-8")

    # In-process checks of the settings and the passive heuristic.
    guard = load_guard()
    guard.SKIPPED_PATHS.append("*/vendor/*")
    check(not guard.is_doc("C:\\work\\vendor\\README.md") and not guard.is_doc("lib/Vendor/a.md")
          and guard.is_doc("docs/guide.md"),
          "SKIPPED_PATHS skips a matching path, backslashes and any case included")
    check(not guard.is_passive("It is often useful.") and not guard.is_passive("The door is open.")
          and guard.is_passive("The key is never shown.") and guard.is_passive("It gets deleted.")
          and not guard.is_passive("Stored encrypted.") and not guard.is_passive("Run in a terminal."),
          "the passive heuristic tells participles from look-alikes and steps")

    print("ok" if bad == 0 else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
