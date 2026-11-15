"""Self-test for guard_test_reruns.py. Run with any Python 3.9+ and git; every
line says "ok", and the last line is "ok" when all cases pass (exit 0).

It builds a throwaway git repository, writes run records into it the way
conftest_run_record.py does, and sends the hook the commands a session
would send. The repository's folder name holds an accented letter, built with
chr(), and the hook gets its input as Claude Code sends it, raw UTF-8 bytes;
one check runs it behind a strict cp1252 console, as on Windows
(hook_io.py)."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ beside the templates
from hook_io import behind_cp1252, run_hook

HERE = Path(__file__).resolve().parent
HOOK = HERE.parent / "guard_test_reruns.py"
sys.path.insert(0, str(HERE.parent))
import guard_test_reruns as guard  # noqa: E402

#: The repository's folder: "repo-cafe" with an accented e, as in a user
#: folder named after a person.
REPO_NAME = "repo-caf" + chr(0xE9)


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=Self Test", "-c", "user.email=selftest@example.invalid",
                           "-c", "core.autocrlf=false", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def now_iso(hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def record(repo, **fields):
    write(repo, guard.RECORD, json.dumps(fields))


def event_for(tool, command, cwd):
    return {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}


def hook(tool, command, cwd, log):
    out = run_hook(HOOK, event_for(tool, command, cwd), TEST_RERUN_GUARD_LOG=log)
    if out.returncode != 0:
        return "crash", out.stderr
    if not out.stdout.strip():
        return "pass", ""
    spec = json.loads(out.stdout)["hookSpecificOutput"]
    return spec["permissionDecision"], spec["permissionDecisionReason"]


class Run:
    def __init__(self, log):
        self.bad = 0
        self.calls = 0
        self.log = log

    def expect(self, label, tool, command, cwd, refused, *wanted):
        decision, reason = hook(tool, command, cwd, self.log)
        if tool in guard.TOOLS:
            self.calls += 1
        ok = (decision == "deny") == refused and decision != "crash" \
            and all(w in reason for w in wanted)
        self.bad += not ok
        print("ok  " if ok else "BAD ", f"{label}: ({tool}) {command}", "" if ok else f"-> {decision}: {reason}")

    def check(self, label, ok, detail=""):
        self.bad += not ok
        print("ok  " if ok else "BAD ", label, "" if ok else detail)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / REPO_NAME
        repo.mkdir()
        log = str(Path(tmp) / "guard.log")
        run = Run(log)
        git(repo, "init", "-q")
        write(repo, "src/app.py", "TOTAL = 1\n")
        write(repo, "tests/test_a.py", "def test_one():\n    assert True\n")
        write(repo, "docs/guide.md", "# Guide\n")
        write(repo, "README.md", "# Project\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "Start")
        head = git(repo, "rev-parse", "HEAD").strip()

        # (a) The last full run passed on this tree.
        record(repo, tests=1, seconds=1.0, finished_utc=now_iso(), passed=True,
               tree=guard.tree_fingerprint(repo))
        for tool, command in [
            ("Bash", "pytest"),
            ("Bash", "python -m pytest -n 4 -q"),
            ("PowerShell", ".\\.venv\\Scripts\\python.exe -m pytest tests"),
            ("PowerShell", "& .\\.venv\\Scripts\\python.exe -m pytest -p no:cacheprovider"),
            ("Bash", "PYTHONDONTWRITEBYTECODE=1 uv run pytest"),
            ("Bash", "cd docs && pytest .."),
            ("Bash", "git status; pytest -x"),
        ]:
            run.expect("same tree: a full run is refused", tool, command, repo, True,
                       "same tree", "# full-run-again")
        written = behind_cp1252(HOOK, event_for("Bash", "pytest", repo), TEST_RERUN_GUARD_LOG=log)
        run.calls += 1
        run.check("behind a cp1252 console the accented folder name is read",
                  '"deny"' in written, written)
        for tool, command in [
            ("Bash", "pytest tests/test_a.py"),
            ("Bash", "pytest tests/test_a.py::test_one"),
            ("Bash", "pytest -k invoices"),
            ("Bash", "pytest -kinvoices"),
            ("Bash", "pytest --lf"),
            ("Bash", "pytest docs"),
            ("Bash", "pytest  # full-run-again"),
            ("Bash", "echo pytest"),
            ("Read", "pytest"),
        ]:
            run.expect("same tree: a narrowed run, the marker or no run passes", tool, command,
                       repo, False)
        write(repo, ".claude/logs/guard_shell_habits.log", "a line\n")
        write(repo, "src/__pycache__/app.cpython-312.pyc", "bytes\n")
        run.expect("same tree: a new log or compiled file is no change", "Bash", "pytest", repo, True)
        write(repo, "src/app.py", "TOTAL = 2\n")
        run.expect("same tree: a changed program file lets the full run go", "Bash", "pytest",
                   repo, False)
        write(repo, "src/app.py", "TOTAL = 1\n")
        record(repo, tests=1, seconds=1.0, finished_utc=now_iso(), passed=True)
        run.expect("same tree: a record with no tree (files changed during the run) refuses nothing",
                   "Bash", "pytest", repo, False)

        # (b) The last full run failed one test.
        failed_run = dict(tests=2, seconds=1.0, finished_utc=now_iso(), passed=False,
                          tree=guard.tree_fingerprint(repo), failed=["tests/test_a.py::test_one"],
                          files=guard.files_against(repo, head))
        record(repo, **failed_run)
        run.expect("failed run: nothing changed since, the failed file is named", "Bash", "pytest",
                   repo, True, "rerun the failed tests only", "`pytest tests/test_a.py`")
        record(repo, **dict(failed_run, failed=[f"tests/test_a.py::test_{i}" for i in range(21)]))
        run.expect("failed run: many failures on an unchanged tree are not a passing tree", "Bash",
                   "pytest", repo, False)
        record(repo, **failed_run)
        write(repo, "tests/test_b.py", "def test_two():\n    assert True\n")
        write(repo, "docs/guide.md", "# Guide, fixed\n")
        run.expect("failed run: tests and documents changed, the test files are named", "Bash",
                   "python -m pytest -n 8", repo, True,
                   "`pytest tests/test_a.py tests/test_b.py`", "docs/guide.md", "# full-run-again")
        run.expect("failed run: the marker lets a full run through", "Bash",
                   "python -m pytest -n 8  # full-run-again", repo, False)
        run.expect("failed run: a narrowed run passes", "Bash", "pytest tests/test_a.py", repo, False)
        git(repo, "add", "tests", "docs")
        git(repo, "commit", "-q", "-m", "Fix the test")
        run.expect("failed run: a commit of only tests and documents still counts", "Bash", "pytest",
                   repo, True, "tests/test_b.py")
        write(repo, "src/app.py", "TOTAL = 3\n")
        run.expect("failed run: a changed program file lets the full run go", "Bash", "pytest",
                   repo, False)
        write(repo, "src/app.py", "TOTAL = 1\n")
        for shared, text in [("tests/conftest.py", "import pytest\n"),
                             ("tests/helpers.py", "VALUE = 1\n"),
                             ("tests/data/invoice.json", "{}\n")]:
            write(repo, shared, text)
            run.expect(f"failed run: a changed {shared} (it can change every test) lets the full "
                       "run go", "Bash", "pytest", repo, False)
            (repo / shared).unlink()
        write(repo, "tests/unit/invoice_test.py", "def test_three():\n    assert True\n")
        run.expect("failed run: a test file in a subfolder still counts as a test", "Bash", "pytest",
                   repo, True, "`pytest tests/test_a.py tests/test_b.py tests/unit/invoice_test.py`")
        (repo / "tests/unit/invoice_test.py").unlink()

        def fresh_failed_record():
            record(repo, **dict(failed_run, files=guard.files_against(repo, head)))

        # A changed test file can break the test files that import it.
        for shared, user, text in [
            ("tests/test_shared.py", "tests/test_user.py", "from tests.test_shared import helper\n"),
            ("tests/test_shared.py", "tests/test_user.py", "import tests.test_shared as shared\n"),
            ("tests/test_shared.py", "tests/test_user.py", "from tests import test_shared\n"),
            ("tests/test_shared.py", "tests/test_user.py",
             "from tests import (\n    test_other,\n    test_shared,\n)\n"),
            ("tests/test_shared.py", "tests/test_user.py",
             "def test_two():\n    from tests.test_shared import db\n"),
            ("tests/unit/shared_test.py", "tests/test_user.py",
             "from tests.unit.shared_test import helper\n"),
            ("tests/unit/shared_test.py", "tests/unit/test_user.py",
             "from .shared_test import helper\n"),
            ("tests/unit/shared_test.py", "tests/unit/test_user.py", "from . import shared_test\n"),
        ]:
            write(repo, shared, "def helper():\n    return 1\n")
            write(repo, user, text)
            fresh_failed_record()
            write(repo, shared, "def helper():\n    return 2\n")
            files = " ".join(sorted({"tests/test_a.py", shared, user}))
            run.expect(f"failed run: {user} imports the changed {shared} ({text.splitlines()[0]})",
                       "Bash", "pytest", repo, True, f"`pytest {files}`")
            (repo / shared).unlink()
            (repo / user).unlink()
        for text in ["from tests.test_shared_more import helper\n",
                     "NAME = 'from tests.test_shared import helper'\n",
                     "from .test_shared import helper\n"]:
            write(repo, "tests/test_shared.py", "def helper():\n    return 1\n")
            write(repo, "tests/unit/test_user.py", text)
            fresh_failed_record()
            write(repo, "tests/test_shared.py", "def helper():\n    return 2\n")
            run.expect(f"failed run: a file that does not import the changed one is left out "
                       f"({text.strip()})", "Bash", "pytest", repo, True,
                       "`pytest tests/test_a.py tests/test_shared.py`")
            (repo / "tests/test_shared.py").unlink()
            (repo / "tests/unit/test_user.py").unlink()
        write(repo, "tests/test_shared.py", "def helper():\n    return 1\n")
        write(repo, "tests/test_user.py", "from tests.test_shared import helper\n")
        git(repo, "add", "tests")
        git(repo, "commit", "-q", "-m", "Shared helper")
        fresh_failed_record()
        (repo / "tests/test_shared.py").unlink()
        run.expect("failed run: a test file that imports a deleted one is named", "Bash", "pytest",
                   repo, True, "`pytest tests/test_a.py tests/test_user.py`")
        git(repo, "rm", "-q", "--cached", "tests/test_shared.py")
        git(repo, "rm", "-q", "tests/test_user.py")
        git(repo, "commit", "-q", "-m", "Remove the shared helper")

        # A changed document can break the tests that read it.
        for doc, text in [("docs/guide.md", "DOC = ROOT / 'docs' / 'guide.md'\n"),
                          ("docs/guide.md", "DOC = 'docs/guide.md'\n"),
                          ("README.md", "TEXT = (ROOT / 'README.md').read_text()\n")]:
            write(repo, "tests/test_reads.py", text)
            write(repo, "tests/test_other.py", "DOC = 'docs/index-guide.md'\n")
            fresh_failed_record()
            write(repo, doc, (repo / doc).read_text(encoding="utf-8") + "More.\n")
            run.expect(f"failed run: a test file that names the changed {doc} is named", "Bash",
                       "pytest", repo, True, "`pytest tests/test_a.py tests/test_reads.py`")
            (repo / "tests/test_reads.py").unlink()
            (repo / "tests/test_other.py").unlink()

        # The test folders are a setting: the test-file pattern follows it.
        source = HOOK.read_text(encoding="utf-8")
        variant = {"__name__": "guard_variant"}
        setting = 'TEST_DIRS = ("tests",)'
        exec(compile(source.replace(setting, 'TEST_DIRS = ("checks",)'), str(HOOK), "exec"), variant)
        run.check("TEST_DIRS decides which paths are test files",
                  source.count(setting) == 1
                  and variant["DOC_OR_TEST"].search("checks/test_x.py") is not None
                  and variant["DOC_OR_TEST"].search("tests/test_x.py") is None
                  and variant["TEST_FILE"].search("checks/unit/x_test.py") is not None)
        run.check("a test-shaped name outside the test folders is no test file",
                  guard.TEST_FILE.search("docs/test_tool.py") is None
                  and guard.TEST_FILE.search("src/test_app.py") is None)
        record(repo, **failed_run)
        record(repo, **dict(failed_run, finished_utc=now_iso(hours_ago=30)))
        run.expect("failed run: a run older than MAX_HOURS refuses nothing", "Bash", "pytest",
                   repo, False)
        record(repo, **dict(failed_run, failed=[f"tests/test_a.py::test_{i}" for i in range(21)]))
        run.expect("failed run: more than MAX_FAILED failures refuses nothing", "Bash", "pytest",
                   repo, False)
        record(repo, **dict(failed_run, finished_utc=datetime.now().isoformat()))
        run.expect("failed run: a time with no zone refuses nothing", "Bash", "pytest", repo, False)
        record(repo, **dict(failed_run, failed=[]))
        run.expect("failed run: no failed ids refuses nothing", "Bash", "pytest", repo, False)

        # Faults let the command through.
        write(repo, guard.RECORD, "not json")
        run.expect("an unreadable record refuses nothing", "Bash", "pytest", repo, False)
        plain = Path(tmp) / "plain"
        plain.mkdir()
        run.expect("outside a git repository nothing is refused", "Bash", "pytest", plain, False)
        out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                             capture_output=True, text=True)
        run.check("unreadable input lets the call through", out.returncode == 0 and not out.stdout.strip())

        lines = Path(log).read_text(encoding="utf-8").splitlines()
        run.check(f"the log has one line per shell call ({len(lines)} lines)",
                  len(lines) == run.calls and any("\tdeny\t" in x for x in lines)
                  and any("\tpass\t" in x for x in lines), f"{len(lines)} != {run.calls}")
    print("ok" if not run.bad else f"FAILED ({run.bad})")
    return 1 if run.bad else 0


if __name__ == "__main__":
    sys.exit(main())
