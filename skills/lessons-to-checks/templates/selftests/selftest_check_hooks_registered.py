"""Self-test for check_hooks_registered.py. Run with any Python 3.9+; every
line says "ok", and the last line is "ok" when all cases pass (exit 0)."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check_hooks_registered.py"


def settings_naming(*names):
    return json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": f'python "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/{n}"'}
        for n in names]}]}}, indent=2)


def check(hooks, *settings):
    args = [sys.executable, str(SCRIPT), "--hooks", str(hooks)]
    for s in settings:
        args += ["--settings", str(s)]
    out = subprocess.run(args, capture_output=True, text=True)
    return out.returncode, out.stdout


def main():
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        hooks = Path(tmp) / "hooks"
        hooks.mkdir()
        for name in ("guard_shell_habits.py", "reply_checks.py", "test_reply_checks.py",
                     "selftest_guard_shell_habits.py", "notes.md"):
            (hooks / name).write_text("# placeholder\n", encoding="utf-8")
        main_settings = Path(tmp) / "settings.json"
        local_settings = Path(tmp) / "settings.local.json"

        main_settings.write_text(settings_naming("reply_checks.py"), encoding="utf-8")
        code, out = check(hooks, main_settings)
        ok = code == 1 and "UNREGISTERED: guard_shell_habits.py" in out and "reply_checks.py is" not in out
        bad += not ok
        print("ok  " if ok else "BAD ", "a hook in no settings file is named; tests and notes are skipped")

        local_settings.write_text(settings_naming("guard_shell_habits.py"), encoding="utf-8")
        code, out = check(hooks, main_settings, local_settings)
        ok = code == 0 and out.startswith("ok")
        bad += not ok
        print("ok  " if ok else "BAD ", "a hook registered in a second settings file counts")

        main_settings.write_text(settings_naming("reply_checks.py").replace("/", "\\\\"), encoding="utf-8")
        code, out = check(hooks, main_settings, local_settings)
        ok = code == 0
        bad += not ok
        print("ok  " if ok else "BAD ", "a Windows-style path in the settings counts")

        main_settings.write_text(settings_naming("old_reply_checks.py"), encoding="utf-8")
        code, out = check(hooks, main_settings, local_settings)
        ok = code == 1 and "UNREGISTERED: reply_checks.py" in out
        bad += not ok
        print("ok  " if ok else "BAD ", "a similar file name does not count as registration")

        code, out = check(hooks, Path(tmp) / "missing.json")
        ok = code == 1 and out.count("UNREGISTERED") == 2
        bad += not ok
        print("ok  " if ok else "BAD ", "a missing settings file registers nothing")
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
