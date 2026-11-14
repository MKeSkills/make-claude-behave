"""Every hook script in the hooks folder is registered in a settings file.

A hook whose own tests pass but that no settings file lists does nothing:
Claude Code runs only the hooks its settings name. This check reads each
script in the hooks folder and looks for its file name in the given settings
files. It prints:

- "ok" when every hook script is named in at least one settings file; exit 0;
- "UNREGISTERED: <script>" for each one that is not; exit 1.

Scripts whose names start with "test_" or "selftest_" are tests, not hooks,
and are skipped; helpers that are not hooks go in NOT_HOOKS.

Registration is necessary, not sufficient: after registering a hook, start a
new session (or open /hooks) and see it act once on a harmless input that
matches it.

Usage:
    python check_hooks_registered.py --hooks .claude/hooks \\
        --settings .claude/settings.json --settings .claude/settings.local.json

Standard library only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_SUFFIXES = {".py", ".sh", ".ps1", ".js", ".mjs", ".ts"}
NOT_HOOKS: set[str] = set()


def unregistered(hooks_dir: Path, settings: list[Path]) -> list[str]:
    text = ""
    for path in settings:
        try:
            text += "\n" + path.read_text(encoding="utf-8")
        except OSError:
            pass
    flat = text.replace("\\\\", "/").replace("\\", "/")
    missing = []
    for path in sorted(hooks_dir.iterdir()):
        if not path.is_file() or path.suffix not in SCRIPT_SUFFIXES:
            continue
        if path.name.startswith(("test_", "selftest_")) or path.name in NOT_HOOKS:
            continue
        if f"/{path.name}" not in flat and f'"{path.name}' not in flat and f" {path.name}" not in flat:
            missing.append(path.name)
    return missing


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hooks", default=".claude/hooks")
    parser.add_argument("--settings", action="append",
                        help="a settings file; repeat for several "
                             "(default: .claude/settings.json and .claude/settings.local.json)")
    args = parser.parse_args(argv)
    settings = [Path(s) for s in (args.settings or
                                  [".claude/settings.json", ".claude/settings.local.json"])]
    missing = unregistered(Path(args.hooks), settings)
    for name in missing:
        print(f"UNREGISTERED: {name} is in {args.hooks} but in no settings file")
    if missing:
        return 1
    print("ok (every hook script is registered)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
