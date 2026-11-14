# Continuous improvement built-in: lessons-to-programmed checks

A Claude Code plugin with one skill: a method for turning every mistake or
correction into a check that acts on its own.

A mistake that is only written down tends to happen again. The next session
does not read the note at the moment it matters. This skill has Claude
record each mistake as a lesson and build its fix right away, as a hook, a
test or a commit check. Claude then proves the fix by seeing it act, and
keeps every lesson on record. The same checks save tokens and time: they
stop work whose answer is already known, such as a second full test run on
unchanged files or a mistake corrected a second time ("Where it saves
tokens and time" below).

## Where it saves tokens and time

A session spends many of its tokens, and much of its time, on work whose
answer is already known: a test run that repeats the last one, a command
that went wrong before and runs again, or a habit the person has to
correct a second time. Each mechanism below stops one of these before it
starts. Every hook logs each time it acts, so the periodic audit can count
how often it did.

A "round" below means one more exchange: a tool call and its output, or a
reply and the person's answer to it. Each round costs tokens, and it costs
time while Claude works and while the person reads and answers.

### A full test run that repeats the last one

`guard_test_reruns.py`, with `conftest_run_record.py`.

**Where the tokens and time go.** A full run of a large test suite is slow,
the session waits for it, and its output fills the session. A session often
starts another full run that can only say the same thing: on files that
have not changed, or after fixing one failed test.

**How the skill saves them.** The conftest snippet records each full run:
whether it passed, the commit and the uncommitted changes it ran on, and
the tests that failed. The hook reads that record before a full run
starts. It refuses a second full run on a tree that already passed one. It
also refuses a full run after a few failures when only tests or documents
changed since, and names the test files to run instead. A comment in the
command, `# full-run-again`, lets a needed full run through.

**Example.** The last full run failed 2 tests, one in
`tests/test_invoices.py` and one in `tests/test_export.py`. Since then,
only those two test files changed. The hook refuses a new full run, and
its refusal says to run
`pytest tests/test_invoices.py tests/test_export.py`. The session waits
for two test files instead of the whole suite, and reads two files'
output.

### Agents that each run the whole suite

`guard_agent_prompts.py`.

**Where the tokens and time go.** Three builder agents work at the same
time, each on one part of a change. Their prompts say nothing about tests,
so each agent runs the full suite on its own part. Only the run on the
combined changes counts, and that run has to happen anyway. The parallel
runs also compete for the same machine, so every agent finishes later. An
agent asked to start a review agent may be unable to. It reports back, and
the main session starts the review in another round, after a wait.

**How the skill saves them.** The hook refuses an agent prompt that asks
for code to be built or changed without saying whether the agent runs the
full suite. The refusal says which line to add. The hook also refuses a
prompt that asks the agent to start another agent, so the main session
starts every agent itself.

**Example.** The hook refuses the prompt "Fix the date parser in
src/dates.py and add a test." With the line "Run only the tests for
src/dates.py; no full run." added, it goes through. The agent hands back
its change after its own tests. The main session runs one full run once
every part is back.

### A command that went wrong before

`guard_shell_habits.py`.

**Where the tokens and time go.** A command that went wrong before runs
again. It fails, or it gives a wrong answer that looks right. The session
spends a round on the failed attempt, a round finding out what went wrong,
and another running the right command. A wrong answer that reaches a reply
also costs the person the time to spot it and write a correction.

**How the skill saves them.** The hook matches each command against the
habits recorded as lessons, and refuses a match before it runs. The
refusal names the command to use, so the next attempt is the right one.
This skips the failed attempt, its diagnosis and the retry.

**Example.** On a shell with no time-zone database,
`TZ=America/New_York date` prints UTC as if it were New York time. The
hook refuses the command and names a clock that honors the zone. So the
first time the session reads is the correct local time. A report built on
it gives the right hour the first time.

### A reply that repeats a corrected habit

`reply_checks.py`.

**Where the tokens and time go.** A reply repeats a habit the person
already corrected, such as stating the time without reading the clock. The
person reads it, writes the correction, and waits while Claude rewrites the
reply. That is a full round of tokens, and the person's time for each step.

**How the skill saves them.** The Stop hook reads each reply before the
person sees it. When a pattern matches, it stops the reply once and says
what to verify. The fix is one rewrite inside the same turn, before the
person reads anything. The second attempt always goes through, so the check
cannot loop.

**Example.** A draft reply says "it is now 14:05", and no tool call in the
turn read the clock. The hook stops it. Claude reads the clock and corrects
the time. The person reads the corrected reply once, with the right time
in it.

### A fix that exists only on paper

`check_lesson_commit.py`, `check_hooks_registered.py` and
`check_lessons_mapped.py`.

**Where the tokens and time go.** A lesson kept only as a note gets missed.
Each repeat of the mistake costs another round: the mistake, the time to
work out its cause again, the correction, the rework and its test run. A
hook that is built and tested but named in no settings file does nothing,
so the mistake repeats while the lesson reads "fixed". A lesson listed
under no procedure is not read when its task comes up.

**How the skill saves them.**

- `check_lesson_commit.py` refuses a commit that adds a lesson without
  changing a hook, test, script or other code, unless the message says why
  no check is possible. The fix is built the first time, so the next
  occurrence is refused at once instead of being diagnosed again.
- `check_hooks_registered.py` prints `UNREGISTERED` for each hook script
  that no settings file names.
- `check_lessons_mapped.py` prints `MISSING` for each lesson listed under
  no procedure.

**Example.** `guard_shell_habits.py` is copied into `.claude/hooks/` and
its self-test passes, but `.claude/settings.json` does not name it. The
registration check prints `UNREGISTERED: guard_shell_habits.py is in
.claude/hooks but in no settings file`. The gap shows up in one check,
before a session relies on a hook that never runs and someone has to find
out why the mistake came back.

### A document the person has to rewrite

`guard_writing_style.py`.

**Where the tokens and time go.** Claude writes a guide full of phrases
that mark generated text: "rest assured", em dashes, sentence after
sentence in the passive voice. The person reads it, marks the phrases,
writes the correction and waits for the rewrite. The rewrite costs another
round, and the same phrases come back in the next document.

**How the skill saves them.** The hook reads the text before the file is
written, and refuses it once with each hit's line and a fix. Claude
rewrites it in the same turn, before anyone reads the file.

**Example.** A Write of `docs/setup.md` says "Rest assured, nothing is lost
when you close the window." The hook refuses it and names line 3. Claude
writes "The draft stays in your outbox when you close the window." The
person reads the guide once. ("How it keeps generated documents free of
LLM-speak" below has the details.)

### A long lessons file read before every task

The "Lessons that apply here" section at the end of each procedure.

**Where the tokens and time go.** A lessons file grows with every mistake.
Reading all of it before each task spends tokens and time on lessons that
do not apply. Skipping it misses the one that does.

**How the skill saves them.** Each procedure ends with one to three lines
per lesson that applies to its task: what to do instead, and the check
that enforces it. A session reads that short list before the task.

**Example.** In this skill, `procedures/spend-less-tokens.md` lists 4 of
the 14 example lessons in `lessons.md`. A session planning test runs reads
those 4 entries and starts the task.

### The other steps in spend-less-tokens.md

`procedures/spend-less-tokens.md` has more steps. They are habits to
follow, and the skill has no template for them.

- **Batch changes into one test cycle.** Example: three small fixes are
  built, each with its own targeted tests. One full run checks the
  combined changes before they are committed together. The session waits
  for one full run.
- **Run slow tests only when the files they exercise changed.** Example: a
  slow test that runs a deploy script is tied to that script in a table.
  When only a page file changed, the run skips that test and says why, and
  the run finishes without waiting for it.
- **Restart a killed run from where it stopped, with fewer workers.**
  Example: a run with 8 workers runs out of memory after 300 tests passed.
  The restart uses 4 workers and runs only the tests that had not passed,
  so the session waits only for those.
- **Start an agent only for independent or large work.** Example: Claude
  makes a one-line fix in a file already open itself. Briefing an agent
  for it, and waiting for its report, costs more than the edit.
- **Read a big file once, by the lines you need.** Example: search for the
  function, read its lines, and reuse what they said later in the session.

## How it keeps generated documents free of LLM-speak

Two templates read what Claude writes before anyone else does.
`guard_writing_style.py` reads documentation files before Claude writes
them. `reply_checks.py` reads chat replies before the person sees them.

### guard_writing_style.py: documentation files

A PreToolUse hook on the Write, Edit and MultiEdit tools. It reads files
whose extension is in `DOC_EXTENSIONS`: `.md`, `.markdown` and `.rst` by
default. Add `.txt` if your plain-text files are documents people read. It
never reads license files (`LICENSE`, `LICENSE.md`, `LICENCE.txt` and the
like), whose wording is fixed. For a Write it reads the whole new content.
For an Edit or MultiEdit it reads only the new text, so older text in the
file never counts against an edit.

It catches:

- em dashes, and en dashes used as dashes (a range such as pages 10 to 20
  written with an en dash passes);
- negative reassurance: "nothing is lost", "nothing happens", "no
  surprises", "rest assured", "pay nothing", "don't worry", and "simply"
  or "just" used to play a step down ("simply run", "just click");
- tell words: "silently", "seamless", "leverage", "delve", "robust",
  "moat", "legible" and "honestly";
- "X, not Y" contrasts, when a text holds 2 or more and at least one for
  every 15 sentences (`MIN_CONTRASTS`, `SENTENCES_PER_CONTRAST`). Two in a
  short note are listed; three in a README of 300 sentences pass;
- heavy use of the passive voice: a form of "be" or "get" followed by a
  past participle ("is refused", "gets deleted"), in 3 or more sentences
  that make up at least a quarter of all sentences. A step that starts
  with a verb ("Run in a terminal.", "Set to 5 by default.") is not
  passive, and a passive kept where the doer does not matter passes.

Before matching, it leaves out front matter, fenced and indented code
blocks, inline code, URLs, link targets, HTML tags and comments, block
quotes and text in double quotes, straight or curly. A fence or comment
left open runs to the end of the text. A quotation that quotes words of
its own is left out whole. For an Edit, it reads the file to see whether
the text being replaced sits inside a fenced block or an HTML comment, and
treats the new text the same way. Documents quote people word for word,
and a quotation keeps its own words. Text in single quotes is read,
because a single quote is also an apostrophe. It has no check for
aphoristic closing lines ("Small steps, big wins."), because no pattern
tells them apart from an ordinary short sentence. Keep a rule about them
in the project's `CLAUDE.md`.

It reads its input as UTF-8 bytes and writes its answer as UTF-8. On
Windows, Python would otherwise decode the input with the console's code
page (cp1252), and every em dash and curly quote would arrive as other
characters. The other hook templates read and write the same way.

On a hit, it refuses the call once and lists each hit with its line and a
fix. The identical call sent again passes, so a phrase kept on purpose
costs one resend. The hook keeps a hash of each refused call in a small
state file for this. Its log holds one JSON line per call, with each hit's
check, line and matched text and the call's hash, so a short report script
can count, per check, the refusals and how many were sent again unchanged:
those are likely false positives, and a check with many of them needs
narrowing.

Before, a Write of `docs/setup.md`:

```
# Setup

Rest assured, nothing is lost when you close the window.
Simply run the installer.
```

The hook answers:

```
Refused once (writing style) for setup.md:
negative reassurance:
  line 3: Rest assured, nothing is lost when you close the window.  Fix: Say what happens to it instead.
  line 3: Rest assured, nothing is lost when you close the window.  Fix: State the fact; drop the reassurance.
  line 4: Simply run the installer.  Fix: Drop "simply"; describe the step as it is.
Rewrite these, then write again. If every one is meant (a quotation, a passive where the doer does not matter), send the same call again unchanged and it will pass.
```

After, the rewrite that goes through:

```
# Setup

The draft stays in your outbox when you close the window.
Run the installer.
```

### reply_checks.py: chat replies

A Stop hook. Its `CHECKS` list holds pairs of a pattern and an instruction.
When a reply matches, the hook stops it once and tells Claude what to fix;
the second attempt always goes through. The template ships with two
checks: a current time stated with no clock read, and a decision
attributed to the person. Add the phrases you correct in replies the same
way, for example:

```python
{
    "name": "negative reassurance",
    "pattern": re.compile(r"\brest assured\b|\bnothing is lost\b|\bno surprises\b", re.I),
    "ask": "Say what happens instead of what does not.",
},
```

Before, with that entry added, a reply ends:

```
I moved the settings to the new file. Rest assured, nothing is lost.
```

The hook stops it once. After, the reply the person reads:

```
I moved the settings to the new file. The old file keeps a copy until you delete it.
```

### Adding a project's own phrases

1. In `guard_writing_style.py`, add a pair of a pattern and a fix to the
   matching list: `NEGATIVE_REASSURANCE`, `TELL_WORDS`, `DASHES` or
   `CONTRASTS`. Add file types to `DOC_EXTENSIONS`, and paths it must
   never check (a vendored file, a copied changelog) to `SKIPPED_PATHS`.
2. In `reply_checks.py`, add an entry to `CHECKS` for the same phrase in
   replies.
3. Add two self-test cases for each: a text that must be refused, and a
   similar one that must pass. Run
   `python skills/lessons-to-checks/templates/selftests/run_all.py`.
4. Record the correction as a lesson and list it under the writing-style
   procedure (`procedures/writing-style.md`).

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
- **Nine procedures** (`skills/lessons-to-checks/procedures/`):
  record-a-lesson, build-the-check, prove-the-check, map-lessons-to-tasks,
  reply-checks, writing-style, independent-review, periodic-audit and
  spend-less-tokens.
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
  | `guard_writing_style.py` | PreToolUse hook on Write, Edit and MultiEdit that refuses, once, documentation text with em dashes, negative reassurance, tell words, repeated "X, not Y" contrasts or heavy passive voice; it lists each hit with its line and a fix, and the same call sent again passes |
  | `settings-example.json` | How the hooks are registered |

  Each has a self-test in `templates/selftests/`. Run them all with
  `python skills/lessons-to-checks/templates/selftests/run_all.py`; the last
  line reads "ok (all 9 self-tests)". The commit-check and test-run
  self-tests need `git`; the end-to-end part of the run-record self-test
  needs `pytest` and says "skip" without it. The hook self-tests share
  `selftests/hook_io.py`, which sends each hook its input as raw UTF-8
  bytes with UTF-8 mode off, and runs each hook once behind a strict cp1252
  console, as on Windows.

The plugin adds no hooks of its own to your sessions. You choose which
templates to copy into a project and register there.

## Install

In Claude Code:

```
/plugin marketplace add MKeSkills/make-claude-behave
/plugin install lessons-to-checks@make-claude-behave
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
https://github.com/MKeSkills/make-claude-behave/issues.

The full terms are in `LICENSE`: the MIT License with the Commons Clause
condition.
