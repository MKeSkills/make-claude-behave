"""Helpers the hook self-tests share: send a hook its input the way Claude
Code does, as raw UTF-8 bytes, and run a hook behind a cp1252 console.

Claude Code sends a hook's input as UTF-8 bytes. On Windows, Python reads a
pipe with the console's code page (cp1252) unless UTF-8 mode is on, so a
hook that reads sys.stdin as text gets every em dash and curly quote as
other characters, or fails on them. These helpers make that failure show in
the self-tests on any system."""

import importlib.util
import io
import json
import os
import subprocess
import sys


def child_env(**extra):
    """The hook's environment: UTF-8 mode off, no PYTHONIOENCODING, no
    CLAUDE_PROJECT_DIR, plus `extra`."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONIOENCODING", "PYTHONUTF8", "CLAUDE_PROJECT_DIR")}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="0")
    env.update(extra)
    return env


class Result:
    """A finished hook run, its output decoded as UTF-8."""

    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_hook(hook, event=None, raw=None, **env):
    """Run the hook in a child process, `event` (or the text `raw`) sent as
    UTF-8 bytes, special characters unescaped."""
    data = raw if raw is not None else json.dumps(event, ensure_ascii=False)
    out = subprocess.run([sys.executable, str(hook)], input=data.encode("utf-8"),
                         capture_output=True, env=child_env(**env))
    return Result(out.returncode, out.stdout.decode("utf-8", errors="replace"),
                  out.stderr.decode("utf-8", errors="replace"))


def behind_cp1252(hook, event, **env):
    """Run the hook's main() in this process with stdin and stdout set up as
    a strict cp1252 console, as on Windows; return what it wrote, decoded as
    UTF-8 (a marker when it is not UTF-8)."""
    spec = importlib.util.spec_from_file_location("hook_under_test", str(hook))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved_in, saved_out, saved_env = sys.stdin, sys.stdout, dict(os.environ)
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(event, ensure_ascii=False).encode("utf-8")),
                                 encoding="cp1252", errors="strict")
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    os.environ.update(env)
    try:
        module.main()
        sys.stdout.flush()
        written = sys.stdout.buffer.getvalue()
    finally:
        sys.stdin, sys.stdout = saved_in, saved_out
        os.environ.clear()
        os.environ.update(saved_env)
    try:
        return written.decode("utf-8")
    except UnicodeDecodeError:
        return "(not UTF-8) " + repr(written)
