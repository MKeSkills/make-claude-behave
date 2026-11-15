---
name: lessons-to-checks
description: A method for turning every mistake or correction into an enforced check, with procedures and runnable templates; the checks also save tokens and time by refusing repeated test runs, commands that went wrong before and repeated corrections. Use it whenever something went wrong, a person corrected your work, a tool behaved differently than expected, or a rule was broken again - and when recording, fixing, proving or closing a lesson; building a hook, test or commit check from a lesson; adding a reply check; keeping documents Claude writes free of LLM-speak (em dashes, negative reassurance, heavy passive voice); mapping lessons to task procedures; setting up an independent code or design review; running a periodic audit of lessons, decisions and checks; or spending fewer tokens on test runs and agents ("why did the whole suite run again?"). Also use it to adopt the method in a project ("set up lessons and checks here", "make sure this never happens again", "why did this happen again?").
---

# lessons-to-checks

A mistake that is only written down tends to happen again, because the next
session does not read the note at the moment it matters. This skill turns
each mistake into a check that acts on its own: a hook that refuses the
command, a test that fails, a commit check that refuses the commit, or a
reply check that stops the reply.

## The method

1. **Record every lesson at once.** A lesson is a correction from the
   person you work for, a mistake that reached something real, a tool that
   behaved differently than expected, or a decision a later session would
   need. The entry says what happened and what would implement the fix.
2. **Build the fix when the lesson is recorded.** Do not wait for the
   mistake to happen again. Choose the strongest form that can work:
   - a check that blocks the mistake (a hook, a test, a commit check);
   - a rule in a file every session loads;
   - a note, only when no check is possible, and say why.
3. **Prove the fix by seeing it act** before marking the lesson fixed: a
   hook refusing a harmless command that matches it, a test failing on the
   old behavior, a commit check refusing. A hook must also be registered in
   a settings file and seen firing in a session. A hook whose own tests pass
   but that no settings file lists does nothing.
4. **Never delete a lesson.** Mark it fixed, with the check that enforces
   it, or canceled, with who canceled it and why.
5. **List each lesson under the task procedures it applies to.** A session
   reads that list before doing the task. A test fails when a lesson is
   listed nowhere.
6. **Stop replies that repeat a corrected writing habit.** A Stop hook
   matches the reply against patterns and stops it once with an
   instruction; the second attempt goes through. A PreToolUse hook does the
   same for documentation files Claude writes (procedures/writing-style.md).
7. **Have significant changes and designs reviewed** by an agent that has
   not seen the work.
8. **Audit periodically**: lessons, decisions, checks and their firing
   rates.

## How to call a procedure

- By name: `/lessons-to-checks:lessons-to-checks record-a-lesson`. The
  argument is a file name in `procedures/`, without `.md`.
- By describing the task ("this happened again", "review this before I
  commit"). Pick the matching procedure below and open its file.

Several procedures chain: a new lesson runs record-a-lesson, then
build-the-check, prove-the-check and map-lessons-to-tasks.

## Lessons first

Before following a procedure, read its "Lessons that apply here" section at
the end of its file. Each line names a lesson by its date and short name,
exactly as the lesson's first line gives them, says what to do instead, and
names the check that enforces it. The lessons in this skill are examples,
kept in `lessons.md` beside this file. In a project, the project's own
lessons file and procedures take their place.

## The procedures

1. [record-a-lesson](procedures/record-a-lesson.md): something went wrong,
   someone corrected your work, or a tool surprised you.
2. [build-the-check](procedures/build-the-check.md): choose and build the
   check that enforces a lesson.
3. [prove-the-check](procedures/prove-the-check.md): see the check act,
   then mark the lesson fixed.
4. [map-lessons-to-tasks](procedures/map-lessons-to-tasks.md): list each
   lesson under the procedures it applies to.
5. [reply-checks](procedures/reply-checks.md): a mistake in how replies are
   written.
6. [writing-style](procedures/writing-style.md): a document Claude writes
   for others to read, or a correction to the wording of one.
7. [independent-review](procedures/independent-review.md): before
   committing a significant change, or before building a significant
   feature.
8. [periodic-audit](procedures/periodic-audit.md): a monthly look at
   lessons, decisions, checks and their cost.
9. [spend-less-tokens](procedures/spend-less-tokens.md): planning test
   runs, batching changes and starting agents, so no run or agent repeats
   an answer already known.

## Templates

In `templates/`, each with a self-test in `templates/selftests/` that
prints "ok" (run all with `python templates/selftests/run_all.py`). Copy
them into a project and adjust the settings at the top of each file. From
an installed plugin they are in
`${CLAUDE_PLUGIN_ROOT}/skills/lessons-to-checks/templates/`.

| Template | What it does |
|---|---|
| `lessons-template.md` | The lessons file: format, status lines, what counts as a lesson |
| `reply_checks.py` | Stop hook: a list of pattern and instruction pairs; stops a reply once, lets the second attempt through, logs every run |
| `guard_shell_habits.py` | PreToolUse hook: refuses shell commands that went wrong before, saying what to do instead; logs every call |
| `check_lesson_commit.py` | commit-msg check: refuses a commit that adds a lesson without changing code or a `Lesson-fix: none - <why>` line, and one that removes a lesson |
| `check_lessons_mapped.py` | Fails for a lesson listed under no procedure, and for a listed line that names no lesson |
| `check_hooks_registered.py` | Fails for a hook script that no settings file names |
| `guard_test_reruns.py` | PreToolUse hook: refuses a full test run on a tree that already passed one, and a full run after a few failures when only test files (not `conftest.py` or helpers) or documents changed since, naming the files to run (with the test files that import a changed test file or name a changed document); `# full-run-again` lets one through |
| `conftest_run_record.py` | conftest.py snippet: writes the run record that `guard_test_reruns.py` reads, at the end of each full pytest run |
| `guard_agent_prompts.py` | PreToolUse hook on the Agent tool: refuses a prompt that asks for code to be built or changed without saying whether the agent runs the full test suite, one that names the shared scratch folder without a subfolder of the agent's own, and one that asks the agent to start another agent; says which line to add; logs every call |
| `guard_writing_style.py` | PreToolUse hook on Write, Edit and MultiEdit: refuses, once, documentation text with em dashes, negative reassurance, tell words, repeated "X, not Y" contrasts or heavy passive voice, listing each hit with its line and a fix; skips code, URLs, front matter and quotations; the same call sent again passes; logs every call |
| `settings-example.json` | How the hooks are registered |

To adopt the method in a project, follow the section "Adopt it in a
project" of the plugin's README (`${CLAUDE_PLUGIN_ROOT}/README.md`): a
lessons file, procedures with their lessons sections, the hooks copied and
registered, the commit check installed, the two consistency checks in the
test suite, a few lines in the project's `CLAUDE.md`, and each hook seen
firing once in a new session.
