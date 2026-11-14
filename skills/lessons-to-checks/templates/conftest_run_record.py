"""conftest.py snippet: record each full test run, for guard_test_reruns.py.

Copy this file's contents into the conftest.py at the top of your test folder
(for example tests/conftest.py). At the end of every full run of the suite it
writes RECORD, relative to the repository's top folder:

    {"tests": 412, "seconds": 183.4, "finished_utc": "2025-05-19T14:02:11+00:00",
     "passed": false,
     "tree": {"head": "<commit id>", "changes": "<hash of every uncommitted change>"},
     "failed": ["tests/test_invoices.py::test_total"],
     "files": {"tests/test_invoices.py": "<blob id>"}}

- "tree" is the files the run started and ended with. It is left out when a
  file changed during the run, because then neither version was tested in
  full.
- "failed" (the node ids of the tests that failed or errored, relative to the
  repository's top folder) and "files" (every file that differed from the
  run's commit, with its content's git blob id) are written for a failed run
  only.

A run that is not full writes nothing: one given a test file or node id, -k,
-m, --lf, --deselect, --ignore, a run stopped early (-x, --maxfail), and a
collect-only run. Under pytest-xdist only the main process writes.

The record is written to a fresh file and moved into place, so a run cut off
half way cannot leave a partial record. A fault here (git missing, a disk
error) writes nothing and never changes the run's result.

Keep logs/ and __pycache__/ in .gitignore. Both functions below leave them
out anyway (SKIPPED), so the record itself never counts as a change.
tree_fingerprint and files_against are the same as in guard_test_reruns.py;
keep the two copies in step (the self-test compares them).

Standard library only, Python 3.9 or later, git, and pytest to run it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

#: The run record, relative to the repository's top folder.
RUN_RECORD = "logs/last-full-run.json"
#: The test folders: a run given only these (or nothing) is a full run.
RUN_RECORD_TEST_DIRS = ("tests",)
#: Paths left out of every comparison: logs and compiled files.
SKIPPED = re.compile(r"^(logs/|\.claude/logs/)|(^|/)__pycache__/|\.pyc$")
GIT_TIMEOUT = 60

_RUN: dict = {}


def _git(repo, *args, stdin=None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True,
                          check=True, timeout=GIT_TIMEOUT).stdout


def _untracked(repo) -> list:
    names = _git(repo, "ls-files", "-z", "--others", "--exclude-standard").split(b"\0")
    return [p for p in names if p and not SKIPPED.search(p.decode("utf-8", "replace"))]


def tree_fingerprint(repo) -> dict:
    """The commit and a hash of everything that differs from it."""
    head = _git(repo, "rev-parse", "HEAD").decode().strip()
    digest = hashlib.sha256()
    digest.update(_git(repo, "diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv"))
    untracked = _untracked(repo)
    if untracked:
        blobs = _git(repo, "hash-object", "--stdin-paths",
                     stdin=b"".join(p + b"\n" for p in untracked)).split()
        digest.update(b"\0untracked\0")
        for path, blob in zip(untracked, blobs):
            digest.update(path + b" " + blob + b"\n")
    return {"head": head, "changes": digest.hexdigest()}


def files_against(repo, base: str) -> dict:
    """Every file that differs from commit `base`, with its blob id, or "deleted"."""
    names = {p for p in _git(repo, "diff", base, "--name-only", "-z", "--no-renames").split(b"\0")
             if p and not SKIPPED.search(p.decode("utf-8", "replace"))}
    names |= set(_untracked(repo))
    out = {}
    present = sorted(p for p in names if (Path(repo) / p.decode("utf-8")).is_file())
    for p in names - set(present):
        out[p.decode("utf-8")] = "deleted"
    if present:
        blobs = _git(repo, "hash-object", "--stdin-paths",
                     stdin=b"".join(p + b"\n" for p in present)).split()
        for p, blob in zip(present, blobs):
            out[p.decode("utf-8")] = blob.decode()
    return out


def is_full_args(args, rootdir, invocation_dir, top) -> bool:
    """The run's arguments name nothing narrower than the repository or a
    test folder (relative paths are read from the folder pytest started in)."""
    def norm(p) -> str:
        return os.path.normcase(os.path.realpath(str(p)))

    whole = {norm(top), norm(rootdir)} | {norm(Path(top) / d) for d in RUN_RECORD_TEST_DIRS}
    for arg in args:
        # A file, a node id or another folder is not the whole suite.
        path = Path(arg)
        if not path.is_absolute():
            path = Path(invocation_dir) / path
        if norm(path) not in whole:
            return False
    return True


def is_narrowed(option) -> bool:
    """An option that makes the run less than the whole suite."""
    return bool(getattr(option, "keyword", "") or getattr(option, "markexpr", "")
                or getattr(option, "lf", False) or getattr(option, "stepwise", False)
                or getattr(option, "deselect", None) or getattr(option, "ignore", None)
                or getattr(option, "ignore_glob", None) or getattr(option, "collectonly", False))


def repo_relative(nodeid: str, rootdir, top) -> str:
    """A node id with its file part made relative to the repository's top
    folder (pytest gives it relative to its rootdir)."""
    file, sep, rest = nodeid.partition("::")
    try:
        file = (Path(rootdir) / file).resolve().relative_to(Path(top).resolve()).as_posix()
    except ValueError:
        pass
    return file + sep + rest


def write_run_record(path, fields: dict) -> None:
    """Write to a fresh file in the same folder, then move it into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                        prefix=path.name + ".", suffix=".tmp", delete=False)
    try:
        with fresh:
            fresh.write(json.dumps(fields, indent=2) + "\n")
        os.replace(fresh.name, path)
    except BaseException:
        Path(fresh.name).unlink(missing_ok=True)
        raise


def _top(config):
    try:
        return Path(_git(config.rootpath, "rev-parse", "--show-toplevel").decode().strip())
    except (OSError, subprocess.SubprocessError):
        return None


def pytest_sessionstart(session):
    config = session.config
    if hasattr(config, "workerinput"):  # a pytest-xdist worker
        return
    _RUN.clear()
    _RUN["start"] = time.perf_counter()
    try:
        _RUN["top"] = _top(config)
        _RUN["tree"] = tree_fingerprint(_RUN["top"]) if _RUN["top"] else None
    except (OSError, subprocess.SubprocessError):
        _RUN["tree"] = None


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if hasattr(config, "workerinput") or not _RUN.get("top"):
        return
    try:
        top = _RUN["top"]
        if int(exitstatus) not in (0, 1) or session.shouldstop or session.shouldfail:
            return
        if is_narrowed(config.option) or not is_full_args(
                config.args, config.rootpath, config.invocation_params.dir, top):
            return
        start = _RUN.get("tree")
        tree = start if start and start == tree_fingerprint(top) else None
        passed = int(exitstatus) == 0
        fields = {
            "tests": session.testscollected,
            "seconds": round(time.perf_counter() - _RUN["start"], 2),
            "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "passed": passed,
        }
        if tree:
            fields["tree"] = tree
        if not passed and tree:
            reporter = config.pluginmanager.get_plugin("terminalreporter")
            stats = getattr(reporter, "stats", {}) or {}
            ids = {getattr(r, "nodeid", "") for key in ("failed", "error")
                   for r in stats.get(key, [])}
            fields["failed"] = sorted(repo_relative(i, config.rootpath, top) for i in ids if i)
            fields["files"] = files_against(top, tree["head"])
        write_run_record(Path(top) / RUN_RECORD, fields)
    except Exception:  # noqa: BLE001 - a fault here never changes the run's result
        return
