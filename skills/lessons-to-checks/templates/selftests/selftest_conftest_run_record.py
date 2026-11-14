"""Self-test for conftest_run_record.py. Run with any Python 3.9+ and git;
every line says "ok", and the last line is "ok" when all cases pass (exit 0).

The first cases test the snippet's functions. When pytest is installed, the
rest copy the snippet into a throwaway repository as tests/conftest.py, run
pytest there, read the record it writes, and send guard_test_reruns.py the
next full run, end to end. Without pytest those cases are skipped and say so."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SNIPPET = HERE.parent / "conftest_run_record.py"
HOOK = HERE.parent / "guard_test_reruns.py"
sys.path.insert(0, str(HERE.parent))
sys.dont_write_bytecode = True
import conftest_run_record as snip  # noqa: E402
import guard_test_reruns as guard  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=Self Test", "-c", "user.email=selftest@example.invalid",
                           "-c", "core.autocrlf=false", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pytest(repo, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                          cwd=repo, capture_output=True, text=True, env=env)


def hook(command, cwd, log):
    event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env.update(TEST_RERUN_GUARD_LOG=log, PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                         capture_output=True, text=True, env=env)
    if not out.stdout.strip():
        return "pass", ""
    spec = json.loads(out.stdout)["hookSpecificOutput"]
    return spec["permissionDecision"], spec["permissionDecisionReason"]


def main():
    bad = 0

    def check(label, ok, detail=""):
        nonlocal bad
        bad += not ok
        print("ok  " if ok else "BAD ", label, "" if ok else detail)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        full = [([], True), (["tests"], True), ([str(root)], True), ([str(root / "tests")], True),
                (["tests/test_ok.py"], False), (["tests/test_ok.py::test_ok"], False),
                (["docs"], False)]
        for args, want in full:
            got = snip.is_full_args(args, root, root, root)
            check(f"is_full_args({args}) is {want}", got == want, f"-> {got}")
        for option, want in [(SimpleNamespace(), False), (SimpleNamespace(keyword="money"), True),
                             (SimpleNamespace(markexpr="slow"), True), (SimpleNamespace(lf=True), True),
                             (SimpleNamespace(deselect=["tests/test_ok.py::test_ok"]), True),
                             (SimpleNamespace(collectonly=True), True)]:
            got = snip.is_narrowed(option)
            check(f"is_narrowed({vars(option)}) is {want}", got == want, f"-> {got}")
        got = snip.repo_relative("test_ok.py::test_ok[1]", root / "tests", root)
        check("a node id is made relative to the repository", got == "tests/test_ok.py::test_ok[1]", got)

        target = root / "logs" / "last-full-run.json"
        snip.write_run_record(target, {"passed": True})
        leftovers = [p.name for p in target.parent.iterdir() if p.name != target.name]
        check("the record is written whole, with no temporary file left",
              json.loads(target.read_text(encoding="utf-8")) == {"passed": True} and not leftovers,
              str(leftovers))
        target.unlink()

        # The two copies of the git functions agree, on a tree with every kind of change.
        git(root, "init", "-q")
        write(root, "src/app.py", "TOTAL = 1\n")
        write(root, "docs/guide.md", "# Guide\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "Start")
        head = git(root, "rev-parse", "HEAD").strip()
        write(root, "src/app.py", "TOTAL = 2\n")
        write(root, "src/new.py", "X = 1\n")
        (root / "docs" / "guide.md").unlink()
        write(root, "logs/other.json", "{}\n")
        check("tree_fingerprint is the same in the hook and the snippet",
              snip.tree_fingerprint(root) == guard.tree_fingerprint(root))
        files = snip.files_against(root, head)
        check("files_against is the same in the hook and the snippet",
              files == guard.files_against(root, head), str(files))
        check("files_against lists changed, new and deleted files, and leaves logs out",
              set(files) == {"src/app.py", "src/new.py", "docs/guide.md"}
              and files["docs/guide.md"] == "deleted", str(files))

        if importlib.util.find_spec("pytest") is None:
            print("skip the end-to-end pytest run: pytest is not installed")
            print("ok" if not bad else f"FAILED ({bad})")
            return 1 if bad else 0

        repo = Path(tmp) / "project"
        repo.mkdir()
        log = str(Path(tmp) / "guard.log")
        record = repo / snip.RUN_RECORD
        git(repo, "init", "-q")
        write(repo, "pytest.ini", "[pytest]\ntestpaths = tests\n")
        write(repo, "tests/conftest.py", SNIPPET.read_text(encoding="utf-8"))
        write(repo, "tests/test_ok.py", "def test_ok():\n    assert True\n")
        write(repo, "tests/test_bad.py", "def test_bad():\n    assert 1 == 2\n")
        write(repo, "src/app.py", "TOTAL = 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "Start")
        head = git(repo, "rev-parse", "HEAD").strip()

        out = pytest(repo)
        data = json.loads(record.read_text(encoding="utf-8")) if record.exists() else {}
        check("a failed full run records the failed test, the tree and the files",
              out.returncode == 1 and data.get("passed") is False and data.get("tests") == 2
              and data.get("failed") == ["tests/test_bad.py::test_bad"]
              and data.get("tree", {}).get("head") == head and data.get("files") == {},
              out.stdout[-400:] + json.dumps(data))
        decision, reason = hook("pytest", repo, log)
        check("the hook then refuses a full run and names the failed file",
              decision == "deny" and "`pytest tests/test_bad.py`" in reason, reason)

        write(repo, "tests/test_bad.py", "def test_bad():\n    assert 2 == 2\n")
        before = record.read_bytes()
        out = pytest(repo, "tests/test_bad.py")
        check("a run of one file passes and leaves the record as it was",
              out.returncode == 0 and record.read_bytes() == before, out.stdout[-400:])
        decision, reason = hook("python -m pytest", repo, log)
        check("with only the test fixed, the hook still names the file to run",
              decision == "deny" and "tests/test_bad.py" in reason, reason)

        out = pytest(repo)
        data = json.loads(record.read_text(encoding="utf-8"))
        check("a passing full run records passed and the tree it ran on",
              out.returncode == 0 and data.get("passed") is True
              and data.get("tree") == guard.tree_fingerprint(repo)
              and "failed" not in data and "files" not in data, json.dumps(data))
        decision, reason = hook("pytest", repo, log)
        check("the hook then refuses the same full run again",
              decision == "deny" and "same tree" in reason, reason)

        before = record.read_bytes()
        out = pytest(repo, "-k", "ok")
        check("a run narrowed with -k leaves the record as it was",
              out.returncode == 0 and record.read_bytes() == before, out.stdout[-400:])
        write(repo, "src/app.py", "TOTAL = 2\n")
        decision, _ = hook("pytest", repo, log)
        check("a changed program file lets the full run go", decision == "pass")

        write(repo, "tests/test_writes.py",
              "from pathlib import Path\n\n\ndef test_writes():\n"
              "    (Path(__file__).parent.parent / 'src' / 'made.py').write_text('X = 1\\n')\n")
        out = pytest(repo)
        data = json.loads(record.read_text(encoding="utf-8"))
        check("a file written during the run leaves the tree out of the record",
              out.returncode == 0 and data.get("passed") is True and "tree" not in data,
              json.dumps(data))
        decision, _ = hook("pytest", repo, log)
        check("and the hook then refuses nothing", decision == "pass")
    print("ok" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
