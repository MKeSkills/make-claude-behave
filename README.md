# lessons-to-checks

A Claude Code plugin with one skill: a method for turning every mistake or
correction into a check that acts on its own.

A mistake that is only written down tends to happen again. The next session
does not read the note at the moment it matters. This skill has Claude
record each mistake as a lesson and build its fix right away, as a hook, a
test or a commit check. Claude then proves the fix by seeing it act, and
keeps every lesson on record.

## What is in it

- **The method** (`skills/lessons-to-checks/SKILL.md`):
  1. Record every mistake or correction at once, as a lesson: what
     happened, and what would implement the fix.
  2. Build the fix when the lesson is recorded, as a check that acts on its
     own: a hook, a test or a commit check. A note alone only when no check
     is possible, with the reason.
  3. Prove the fix by seeing it act before marking the lesson fixed. A hook
     is registered in a settings file and seen firing in a session.
  4. Never delete a lesson. Mark it fixed or canceled.
  5. List each lesson under the task procedures it applies to. A test fails
     when one is listed nowhere.
  6. Stop a reply that repeats a corrected writing habit, once, with a reply
     check.
  7. Have significant changes and designs reviewed by an agent that has not
     seen the work.
  8. Audit lessons, decisions and checks periodically.
- **Eight procedures** (`skills/lessons-to-checks/procedures/`):
  record-a-lesson, build-the-check, prove-the-check, map-lessons-to-tasks,
  reply-checks, independent-review, periodic-audit and spend-less-tokens.
  Each ends with the lessons that apply to it.
- **Templates you copy into a project**
  (`skills/lessons-to-checks/templates/`), in plain Python with no
  dependencies:

  | Template | What it does |
  |---|---|
  | `lessons-template.md` | The lessons file: format, status lines, what counts as a lesson |
  | `guard_shell_habits.py` | PreToolUse hook that refuses shell commands that went wrong before, and says what to do instead |
  | `reply_checks.py` | Stop hook that stops a reply once when a pattern matches; the second attempt goes through |
  | `check_lesson_commit.py` | commit-msg check that refuses a lesson added without a code change (or a `Lesson-fix: none - <why>` line), and a lesson removed |
  | `check_lessons_mapped.py` | Fails for a lesson listed under no procedure |
  | `check_hooks_registered.py` | Fails for a hook script that no settings file names |
  | `guard_test_reruns.py` | PreToolUse hook that refuses a full test run on a tree that already passed one, and a full run after a few failures when only tests or documents changed since; it names the test files to run, and `# full-run-again` in the command lets a needed full run through |
  | `conftest_run_record.py` | A conftest.py snippet that writes the run record `guard_test_reruns.py` reads, at the end of each full pytest run |
  | `guard_agent_prompts.py` | PreToolUse hook on the Agent tool that refuses an agent prompt missing a line its work needs: whether the agent runs the full test suite (for a prompt that builds or changes code), a scratch subfolder of the agent's own, and no request to start another agent; it says which line to add |
  | `settings-example.json` | How the hooks are registered |

  Each has a self-test in `templates/selftests/`. Run them all with
  `python skills/lessons-to-checks/templates/selftests/run_all.py`; the last
  line reads "ok (all 8 self-tests)". The commit-check and test-run
  self-tests need `git`; the end-to-end part of the run-record self-test
  needs `pytest` and says "skip" without it.

The plugin adds no hooks of its own to your sessions. You choose which
templates to copy into a project and register there.

## Install

In Claude Code:

```
/plugin marketplace add MKeSkills/lessons-to-checks
/plugin install lessons-to-checks@lessons-to-checks
```

Claude uses the skill when a task matches it ("this happened again",
"record a lesson", "set up lessons and checks here"). You can also call it
by name, with a procedure as the argument:

```
/lessons-to-checks:lessons-to-checks record-a-lesson
```

Requirements: Python 3.9 or later for the templates, and `git` for the
commit check.

## Adopt it in a project

1. **Start the lessons file.** Copy `templates/lessons-template.md` to
   `docs/lessons.md`.
2. **Write procedures for the tasks the project repeats** (a release, a
   code review, a commit message, a reply), one Markdown file each in
   `docs/procedures/`. Each ends with a `## Lessons that apply here`
   section. The skill's own procedures are a starting point.
3. **Copy the hooks** you need into `.claude/hooks/` and register them in
   `.claude/settings.json` (`templates/settings-example.json`). Use the
   Python command that works on your machine (`python`, `python3` or `py`).
   For `guard_test_reruns.py`, also copy `templates/conftest_run_record.py`
   into `tests/conftest.py`, and keep `logs/` and `.claude/logs/` in
   `.gitignore`.
4. **Install the commit check** as a git hook:

   ```
   mkdir -p .githooks
   printf '#!/bin/sh\nexec python .claude/hooks/check_lesson_commit.py "$1"\n' > .githooks/commit-msg
   chmod +x .githooks/commit-msg
   git config core.hooksPath .githooks
   ```

   Set `LESSONS` at the top of the script if your lessons file is not
   `docs/lessons.md`.
5. **Add the two consistency checks to your test suite or CI**:
   `check_lessons_mapped.py --lessons docs/lessons.md --procedures docs/procedures`
   and `check_hooks_registered.py --hooks .claude/hooks`. Both print "ok"
   or name what is wrong.
6. **Tell Claude about it** in the project's `CLAUDE.md`:

   ```
   Lessons are in docs/lessons.md and never deleted. Record each mistake
   or correction there at once and build its check in the same commit
   (the lessons-to-checks skill). Before a task, open its procedure in
   docs/procedures/ and read "Lessons that apply here" first.
   ```

7. **Start a new session and prove each hook fires once**, with a harmless
   input that matches it. Settings are read when a session starts.

## A worked example

A script reported that a nightly job ran at 17:01 local time. It ran at
12:01. The shell had no time-zone database, so `TZ=America/New_York date`
printed UTC.

**1. The lesson**, added to the top of `docs/lessons.md`:

```
- **2025-01-14, a script stated the wrong time zone.** A report said a job
  ran at 17:01 local time; it ran at 12:01. The shell had no time-zone
  database, so `TZ=America/New_York date` printed UTC. What would implement
  it: a PreToolUse hook that refuses `TZ=` with a named zone and says which
  clock to use instead. Status: open.
```

**2. The check**, an entry in `HABITS` in
`.claude/hooks/guard_shell_habits.py` (the template already holds it):

```python
(
    "named time zone in TZ=",
    re.compile(r"(?:^|[\s;&|('\"])(?:export\s+)?TZ=['\"]?[A-Za-z]+/[A-Za-z_]+"),
    "This shell has no time-zone database, so a named zone in TZ= is "
    "ignored and the time printed is UTC (lesson: a script stated the "
    "wrong time zone). Read the local time with a tool that honors the "
    "zone, such as Python's zoneinfo with the tzdata package installed.",
),
```

Its self-test has one command that must be refused,
`TZ=America/New_York date`, and a similar one that must pass,
`TZ=UTC date`.

**3. The hook registered.** Before the settings name it, the registration
check says:

```
$ python check_hooks_registered.py
UNREGISTERED: guard_shell_habits.py is in .claude/hooks but in no settings file
```

After adding the `PreToolUse` entry from `templates/settings-example.json`
to `.claude/settings.json`:

```
$ python check_hooks_registered.py
ok (every hook script is registered)
```

**4. The hook refusing, in a new session.** Asked to run
`TZ=America/New_York date`, Claude gets this back, and the command does not
run:

```
PreToolUse:Bash hook error: Refused (named time zone in TZ=): This shell
has no time-zone database, so a named zone in TZ= is ignored and the time
printed is UTC (lesson: a script stated the wrong time zone). Read the
local time with a tool that honors the zone, such as Python's zoneinfo
with the tzdata package installed.
```

The hook's log, `.claude/logs/guard_shell_habits.log`, gains a line:

```
2025-01-14 12:00:30	deny	named time zone in TZ=
```

**5. The lesson marked fixed**, in place:

```
Status: fixed 2025-01-14, enforced by .claude/hooks/guard_shell_habits.py
("named time zone in TZ="), seen refusing `TZ=America/New_York date`.
```

**6. The lesson listed** under the procedures it applies to, such as
`docs/procedures/scripts.md`:

```
## Lessons that apply here

- **2025-01-14, a script stated the wrong time zone.** Read the local time
  with a clock that honors zones. Check: the shell-habit guard.
```

**7. One commit** holds the entry, the hook, its self-test, the settings
change and the procedure line. The commit check lets it through, because
a hook changed beside the lesson. The same entry committed alone is
refused:

```
commit refused: This commit adds a lesson to docs/lessons.md (a new entry
or a note added to one) but changes no hook, test, script or code. Build
the fix in this commit: a check that refuses the mistake, with its test.
If no check is possible, add the line 'Lesson-fix: none - <why no check
is possible>'.
```

If the mistake happens again, the entry gets a note ("Again 2025-03-02:
...") and the check gets stronger. The entry is never deleted.

## License and commercial use

You may use, copy and change lessons-to-checks for free, including at
work and inside your company's own projects.

Selling it needs a commercial license from MKeSkills, with a royalty. That
covers selling the plugin itself, and selling a product or service whose
value comes mainly from it, such as paid hosting or paid support for it.
To ask for a commercial license, open an issue at
https://github.com/MKeSkills/lessons-to-checks/issues.

The full terms are in `LICENSE`: the MIT License with the Commons Clause
condition.
