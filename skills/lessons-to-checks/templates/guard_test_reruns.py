"""PreToolUse hook: refuse a full test run that would only repeat what the last one said.

A full run of a large test suite takes minutes and, in a Claude Code session,
a large share of the session's tokens. Two kinds of full run add nothing:

(a) **The same tree again.** The last full run passed, and no file has
    changed since: the same commit and the same uncommitted changes. A second
    run gives the same answer.
(b) **A few failures, fixed in tests or documents.** The last full run failed
    1 to MAX_FAILED tests, finished less than MAX_HOURS ago, and every file
    changed since is a test or a document (DOC_OR_TEST). Program code is as
    the run saw it, so only the failed tests' files, and any test file
    changed since, need to run. The refusal names them.

A comment with the marker in the command (`pytest  # full-run-again`) lets
either kind through, for the cases a record cannot see: a dependency
upgraded, a flaky test, a run asked for by name.

The hook reads the run record that the test runner writes at the end of each
full run (templates/conftest_run_record.py, copied into tests/conftest.py).
The record is JSON at RECORD, relative to the repository's top folder:

    {"tests": 412, "seconds": 183.4, "finished_utc": "2025-05-19T14:02:11+00:00",
     "passed": false,
     "tree": {"head": "<commit id>", "changes": "<hash of every uncommitted change>"},
     "failed": ["tests/test_invoices.py::test_total"],
     "files": {"tests/test_invoices.py": "<blob id>", "docs/notes.md": "deleted"}}

"tree" is present only when the files were the same at the start and the end
of the run. "failed" and "files" are present only for a failed run: the node
ids of the tests that failed, and every file that differed from the run's
commit, with its content's git blob id. Tests are identified by their node id
and file versions by their content hash; nothing is matched by time or name
alone.

Keep logs/, .claude/logs/ and __pycache__/ in .gitignore. The hook leaves
them out of its comparison anyway (SKIPPED), so its own log and the record
never count as a change.

Saves tokens and time: a full run's output fills the session, and the
session waits for the whole suite to finish. A repeated full run only says
again what the record already holds. The hook refuses that run before it
starts and names the smaller run that answers the open question. Example:
the last full run failed 2 tests; since then only their two test files
changed; a new full run is refused, and the refusal names
`pytest tests/test_invoices.py tests/test_export.py`. The session waits for
two test files and reads their output, instead of the whole suite's.

Register it (in .claude/settings.json of the project):

    "PreToolUse": [
      {"matcher": "Bash|PowerShell",
       "hooks": [{"type": "command",
                  "command": "python \\"${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_test_reruns.py\\""}]}
    ]

Every call is logged (time, outcome, which check) so the firing rate can be
read at the periodic audit. A fault inside the hook, or git not answering,
lets the command through: a broken check must never stop work.

Standard library only, Python 3.9 or later, and git.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ----------------------------------------------------------------- settings

#: The run record, relative to the repository's top folder.
RECORD = "logs/last-full-run.json"
#: The marker that lets a full run through anyway.
MARKER = "full-run-again"
#: How many failed tests still count as "a few", and how old the run may be.
MAX_FAILED = 20
MAX_HOURS = 24
#: Files whose change never needs program code run again. Adjust to your layout.
DOC_OR_TEST = re.compile(r"^(tests/|docs/)|^[^/]+\.md$")
#: The test folders: `pytest tests` is a full run, `pytest tests/test_x.py` is not.
TEST_DIRS = ("tests",)
#: Paths left out of every comparison: logs (this hook's own, the record) and
#: compiled files.
SKIPPED = re.compile(r"^(logs/|\.claude/logs/)|(^|/)__pycache__/|\.pyc$")
#: Seconds per git call; the hook stays well inside Claude Code's time limit.
GIT_TIMEOUT = 5

#: pytest options that take the next word as their value.
PYTEST_VALUED = {
    "-n", "-k", "-m", "-p", "-c", "-o", "-W", "-r", "--tb", "--basetemp", "--deselect",
    "--maxfail", "--durations", "--rootdir", "--confcutdir", "--ignore", "--ignore-glob",
    "--junitxml", "--junit-xml", "--log-level", "--dist", "--maxprocesses", "--timeout",
    "--import-mode", "--capture", "--override-ini", "--numprocesses", "--cov",
    "--cov-report", "--color", "--log-file", "--log-cli-level",
}
#: pytest options after which the run is not a full run (or runs no tests).
PYTEST_NARROWING = {
    "-k", "-m", "--lf", "--last-failed", "--sw", "--stepwise", "--stepwise-skip",
    "--deselect", "--ignore", "--ignore-glob", "--co", "--collect-only", "--collectonly",
    "--help", "-h", "--version", "-V", "--fixtures", "--markers", "--setup-plan",
}
PYTHON = re.compile(r"^(python[0-9.]*|pythonw|py)$")
RUNNERS = {"uv", "poetry", "pipenv", "hatch", "pdm"}
TOOLS = ("Bash", "PowerShell")

SAME_TREE = (
    "Refused (same tree): this tree already passed a full test run ({record}: "
    "commit {head}, the same uncommitted changes, finished {finished} UTC, "
    "{tests} tests). A second run gives the same answer. Run only the tests "
    "for what changes next, such as `pytest tests/test_<name>.py`. If a full "
    "run is needed anyway (a dependency changed, a flaky test), add the "
    "comment `# {marker}` to the command."
)
RERUN_FAILED = (
    "Refused (rerun the failed tests only): the last full run ({record}, "
    "finished {finished} UTC) failed {count} test(s), and every file changed "
    "since is a test or a document ({changed}). Run only these: "
    "`pytest {files}`. If program code must run in full anyway, add the "
    "comment `# {marker}` to the command."
)


# ---------------------------------------------------------------------- git


def git(repo: str | Path, *args: str, stdin: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True,
                          check=True, timeout=GIT_TIMEOUT).stdout


def _untracked(repo: str | Path) -> list[bytes]:
    names = git(repo, "ls-files", "-z", "--others", "--exclude-standard").split(b"\0")
    return [p for p in names if p and not SKIPPED.search(p.decode("utf-8", "replace"))]


def tree_fingerprint(repo: str | Path) -> dict[str, str]:
    """The commit the checkout is on, and a hash of everything that differs
    from it: staged and unstaged changes, and each untracked file git does
    not ignore, by name and content. Equal fingerprints mean the same files.
    The conftest snippet holds the same function; keep the two in step (the
    self-test compares them)."""
    import hashlib  # noqa: PLC0415

    head = git(repo, "rev-parse", "HEAD").decode().strip()
    digest = hashlib.sha256()
    digest.update(git(repo, "diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv"))
    untracked = _untracked(repo)
    if untracked:
        blobs = git(repo, "hash-object", "--stdin-paths",
                    stdin=b"".join(p + b"\n" for p in untracked)).split()
        digest.update(b"\0untracked\0")
        for path, blob in zip(untracked, blobs):
            digest.update(path + b" " + blob + b"\n")
    return {"head": head, "changes": digest.hexdigest()}


def files_against(repo: str | Path, base: str) -> dict[str, str]:
    """Every file that differs from commit `base` (a commit since, a staged or
    unstaged change, an untracked file), with its content's blob id, or
    "deleted". Same function in the conftest snippet."""
    names = {p for p in git(repo, "diff", base, "--name-only", "-z", "--no-renames").split(b"\0")
             if p and not SKIPPED.search(p.decode("utf-8", "replace"))}
    names |= set(_untracked(repo))
    out: dict[str, str] = {}
    present = sorted(p for p in names if (Path(repo) / p.decode("utf-8")).is_file())
    for p in names - set(present):
        out[p.decode("utf-8")] = "deleted"
    if present:
        blobs = git(repo, "hash-object", "--stdin-paths",
                    stdin=b"".join(p + b"\n" for p in present)).split()
        for p, blob in zip(present, blobs):
            out[p.decode("utf-8")] = blob.decode()
    return out


def top_level(cwd: str) -> str | None:
    try:
        out = git(cwd, "rev-parse", "--show-toplevel").decode().strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


# ------------------------------------------------------- reading commands


def segments(text: str) -> list[list[str]]:
    """The command's simple commands, each as a list of words. Comments are
    dropped; `;`, `&&`, `||`, `|` and new lines separate commands. Words keep
    their backslashes, so Windows paths survive."""
    out = []
    for line in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", line)
        for part in re.split(r"&&|\|\||[;|]", line):
            try:
                words = shlex.split(part, posix=False)
            except ValueError:
                words = part.split()
            words = [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "'\"" else w
                     for w in words]
            if words:
                out.append(words)
    return out


def program(word: str) -> str:
    name = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def pytest_args(words: list[str]) -> list[str] | None:
    """The arguments given to pytest, or None when this is not a pytest run."""
    k = 0
    while k < len(words) and (words[k] in ("&", ".") or re.match(r"^\w+=", words[k])):
        k += 1
    if k < len(words) and program(words[k]) in RUNNERS and words[k + 1:k + 2] == ["run"]:
        k += 2
    if k >= len(words):
        return None
    name = program(words[k])
    if name in ("pytest", "py.test"):
        return words[k + 1:]
    if PYTHON.match(name):
        j = k + 1
        while j < len(words):
            if words[j] == "-m":
                return words[j + 2:] if words[j + 1:j + 2] == ["pytest"] else None
            if words[j] in ("-X", "-W"):
                j += 2
                continue
            if not words[j].startswith("-"):
                return None
            j += 1
    return None


def is_full(args: list[str], cwd: str, repo: str) -> bool:
    """pytest with no test path (or only the repository or a test folder)
    and nothing that narrows the run."""
    def norm(p: str) -> str:
        return os.path.normcase(os.path.realpath(p))

    whole = {norm(repo)} | {norm(os.path.join(repo, d)) for d in TEST_DIRS}
    skip = False
    for word in args:
        if skip:
            skip = False
            continue
        option = word.split("=", 1)[0]
        if option in PYTEST_NARROWING or re.match(r"^-[km].", word):
            return False
        if word.startswith("-"):
            skip = option in PYTEST_VALUED and "=" not in word
            continue
        # A file, a node id (tests/test_x.py::test_y) or another folder is
        # not the repository or a test folder: not a full run.
        path = word if os.path.isabs(word) else os.path.join(cwd, word)
        if norm(path) not in whole:
            return False
    return True


def full_runs(text: str, cwd: str) -> list[str]:
    """The repositories in which the command starts a full pytest run."""
    here, found = cwd, []
    for words in segments(text):
        if program(words[0]) in ("cd", "set-location", "pushd", "sl") and len(words) > 1:
            target = words[-1]
            here = target if os.path.isabs(target) else os.path.join(here, target)
            continue
        args = pytest_args(words)
        if args is None:
            continue
        repo = top_level(here)
        if repo and is_full(args, here, repo):
            found.append(repo)
    return found


# ------------------------------------------------------------------ checks


def read_record(repo: str) -> dict | None:
    try:
        record = json.loads((Path(repo) / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def same_tree(repo: str, record: dict) -> str | None:
    """(a) the last full run passed on exactly these files."""
    if record.get("passed") is not True or not isinstance(record.get("tree"), dict):
        return None
    if tree_fingerprint(repo) != record["tree"]:
        return None
    return SAME_TREE.format(record=RECORD, head=record["tree"].get("head", "?")[:7],
                            finished=record.get("finished_utc", "?"),
                            tests=record.get("tests", "?"), marker=MARKER)


def rerun_failed(repo: str, record: dict, now: datetime | None = None) -> str | None:
    """(b) the last full run failed a few tests, recently, and only tests or
    documents changed since."""
    failed, files, tree = record.get("failed"), record.get("files"), record.get("tree")
    if record.get("passed") is not False or not isinstance(failed, list) \
            or not isinstance(files, dict) or not isinstance(tree, dict):
        return None
    if not 0 < len(failed) <= MAX_FAILED:
        return None
    try:
        finished = datetime.fromisoformat(record["finished_utc"])
    except (KeyError, TypeError, ValueError):
        return None
    if finished.tzinfo is None:
        return None
    if (now or datetime.now(timezone.utc)) - finished > timedelta(hours=MAX_HOURS):
        return None
    current = files_against(repo, tree["head"])
    changed = sorted(p for p in set(current) | set(files) if current.get(p) != files.get(p))
    if any(not DOC_OR_TEST.search(p) for p in changed):
        return None
    targets = {str(n).split("::")[0] for n in failed}
    targets |= {p for p in changed if Path(p).name.startswith("test_") and p.endswith(".py")
                and current.get(p) != "deleted"}
    return RERUN_FAILED.format(record=RECORD, finished=record["finished_utc"],
                               count=len(failed), changed=", ".join(changed) or "none",
                               files=" ".join(sorted(targets)), marker=MARKER)


def reasons(text: str, cwd: str) -> list[tuple[str, str]]:
    """(check name, reason) for each refusal the command earns."""
    if MARKER in text:
        return []
    found = []
    for repo in full_runs(text, cwd):
        record = read_record(repo)
        if not record:
            continue
        for name, check in (("same tree", same_tree), ("rerun failed", rerun_failed)):
            try:
                why = check(repo, record)
            except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError):
                why = None  # git did not answer, or a record it cannot read
            if why:
                found.append((name, why))
    return found


# --------------------------------------------------------------------- hook


def log_path() -> str:
    """TEST_RERUN_GUARD_LOG if set, else the project's .claude/logs folder,
    else a logs folder beside this script."""
    if os.environ.get("TEST_RERUN_GUARD_LOG"):
        return os.environ["TEST_RERUN_GUARD_LOG"]
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    base = os.path.join(project, ".claude") if project else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "logs", "guard_test_reruns.log")


def log(outcome: str, names: list[str]) -> None:
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{outcome}\t{','.join(names) or '-'}\n")
    except OSError:
        pass


def read_event() -> object:
    """The event, read as UTF-8 bytes whatever the console's code page. Read
    as text on Windows, it would be decoded as cp1252, and every em dash and
    curly quote would arrive as other characters."""
    return json.loads(sys.stdin.buffer.read().decode("utf-8"))


def answer(payload: dict) -> None:
    """Write the answer to stdout as UTF-8 whatever the console's code page."""
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def main() -> None:
    try:
        event = read_event()
    except ValueError:
        return
    if not isinstance(event, dict) or event.get("tool_name") not in TOOLS:
        return
    command = (event.get("tool_input") or {}).get("command") or ""
    try:
        found = reasons(command, event.get("cwd") or os.getcwd())
    except Exception:  # noqa: BLE001 - a fault in the check never blocks work
        log("error", [])
        return
    log("deny" if found else "pass", [name for name, _ in found])
    if found:
        answer({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": " ".join(why for _, why in found),
            }
        })


if __name__ == "__main__":
    main()
