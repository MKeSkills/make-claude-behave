# Continuous improvement built-in: lessons-to-programmed checks

lessons-to-checks is a Claude Code plugin with one skill. The skill teaches
Claude to turn every mistake it makes, and every correction you give it,
into a check that acts on its own the next time.

Most people write a mistake down as a note and move on. The note rarely
helps, because the next session doesn't read it at the moment the mistake
is about to happen, and the mistake comes back. With this skill, Claude
records each mistake as a lesson and builds its fix right away, as a hook,
a test or a commit check. A hook is a small script that Claude Code runs
before or after a tool call, and it can stop the call. Claude then proves
that the fix works by watching it catch the mistake once, and it keeps
every lesson on record.

The same checks save you tokens and time. They stop Claude before it
starts work whose result you already know, such as a second full test run
on files that haven't changed, or a mistake you already corrected once.
The next section goes through each check, with an example of what it
saves.

## Where it saves tokens and time

Every exchange in a Claude Code session costs tokens, and most of them
cost time as well: you wait while Claude works, and Claude waits while you
read and answer. Many of those exchanges produce a result you could have
predicted. Three kinds come up most often:

- Claude runs the full test suite again, and the tests that passed in the
  previous run pass again.
- Claude runs a command that went wrong in an earlier session, and it goes
  wrong the same way.
- Claude repeats a habit you already corrected, and you spend another
  message correcting it.

Each check below stops one of these before it starts, so neither you nor
Claude spends anything on it. Every hook also writes a line to its log
each time it acts. When you review your checks, the log shows how often
each one saved you a round, and whether it still earns its place.

This section uses the word "round" for one extra exchange: a tool call and
its output, or a reply from Claude and your answer to it. Each round costs
tokens. It also costs time, both while Claude works and while you read and
respond.

### A full test run that repeats the last one

`guard_test_reruns.py`, with `conftest_run_record.py`.

**Without the check.** A full run of a large test suite can take many
minutes. The session waits for it to finish, and its output takes up room
in the conversation, which Claude pays for in tokens on every later turn.
Sessions often start another full run that can only repeat what the last
one said. Either the files haven't changed since a run that passed, or
Claude fixed the one or two tests that failed and wants to confirm the
fix.

**With the check.** The conftest snippet writes a short record at the end
of every full run: whether the run passed, the commit and uncommitted
changes it ran on, and the tests that failed. Before Claude starts a full
run, the hook reads that record. If the files match a run that passed, the
hook refuses the new run. If the last run failed a few tests and only test
files or documents have changed since, the hook also refuses the full run,
and names the test files Claude should run instead. When a full run really
is needed, Claude adds the comment `# full-run-again` to the command, and
the hook lets it through.

**Example.** The last full run failed 2 tests, one in
`tests/test_invoices.py` and one in `tests/test_export.py`. Claude fixes
both, and changes only those two test files. When Claude tries to start a
new full run, the hook refuses it and tells Claude to run
`pytest tests/test_invoices.py tests/test_export.py`. You wait for two test
files instead of the whole suite, and Claude reads the output of two files
instead of the whole suite's.

### Agents that each run the whole suite

`guard_agent_prompts.py`.

**Without the check.** Claude often splits a change among several builder
agents that work at the same time, each on one part. If their prompts say
nothing about testing, each agent runs the full suite on its own part.
Only the final run on the combined changes tells you whether the parts
work together, and that run has to happen anyway, so the agents' own full
runs add nothing. They also compete for the same processor and memory, so
every agent finishes later. A second waste: Claude sometimes asks an agent
to start a review agent of its own, and a background agent may be unable
to. The agent reports back that it couldn't, and the main session starts
the review itself, one round and one wait later.

**With the check.** The hook reads every agent prompt before the agent
starts. It refuses a prompt that asks the agent to build or change code
without saying whether the agent runs the full suite, and its refusal
gives the line to add. It also refuses a prompt that asks the agent to
start another agent, so the main session starts every agent itself, the
first time.

**Example.** The hook refuses the prompt "Fix the date parser in
src/dates.py and add a test." Claude adds the line "Run only the tests for
src/dates.py; no full run.", and the hook lets the prompt through. The
agent runs only the date parser's tests and hands back its change. Once
every agent has reported, the main session runs the full suite one time,
on the combined changes. With three agents, that is one full run where
there would have been four.

### A command that went wrong before

`guard_shell_habits.py`.

**Without the check.** Claude runs a command that went wrong in an
earlier session. Either it fails again, or it returns a wrong answer that
looks right. A failure costs three rounds: the failed attempt, the work to
find out what went wrong, and the run of the right command. A wrong answer
that looks right can cost more. It reaches a reply or a report, and you
have to spot the mistake and write a correction.

**With the check.** When a command goes wrong in a way that can happen
again, Claude records it as a lesson and adds a pattern for it to the
hook. Before any shell command runs, the hook compares it with those
patterns. When one matches, the hook refuses the command and names the
command to use instead. Claude's next attempt is the right one, and you
save the failed attempt, the search for its cause and the retry.

**Example.** On a shell without a time-zone database,
`TZ=America/New_York date` prints UTC as if it were New York time. The
hook refuses the command and names a clock that honors the time zone. The
first time Claude reads is the correct local time, and a report built on
it states the right hour from the start.

### A reply that repeats a habit you corrected

`reply_checks.py`.

**Without the check.** You corrected a habit, such as stating the time
without reading the clock, and a later reply does it again. You read the
reply, notice the mistake, write the correction, and wait while Claude
rewrites it. That costs a full round of tokens, and your time at every
step.

**With the check.** A Stop hook runs each time Claude finishes a reply,
before you see it. When the reply matches the pattern of a habit you
corrected, the hook holds it back once and tells Claude what to check.
Claude fixes the reply in the same turn, before you read anything. The
hook lets Claude's second attempt through in every case, so a false match
costs one rewrite and the check can't loop.

**Example.** A draft reply says "it is now 14:05", and no tool call in
that turn read the clock. The hook holds the reply back. Claude reads the
clock and corrects the time. You read one reply, with the right time in
it, and write no correction.

### A fix that exists only on paper

`check_lesson_commit.py`, `check_hooks_registered.py` and
`check_lessons_mapped.py`.

**Without the check.** A lesson kept only as a note gets missed at the
moment it matters. Each time the mistake repeats, you pay for it again:
the mistake itself, the time to work out its cause a second time, the
correction, the rework and the test run after it. Two quieter gaps cost
the same way. A hook that someone built and tested but never named in a
settings file never runs, so the mistake repeats while the lesson says
"fixed". A lesson that no procedure lists stays unread when its task comes
up.

**With the check.**

- `check_lesson_commit.py` refuses a commit that adds a lesson without
  changing a hook, test, script or other code, unless the commit message
  explains why no check is possible. Claude builds the fix the first time
  the mistake happens, so the next occurrence meets a refusal at once, and
  nobody has to work out its cause again.
- `check_hooks_registered.py` prints `UNREGISTERED` for each hook script
  that no settings file names.
- `check_lessons_mapped.py` prints `MISSING` for each lesson that no
  procedure lists.

**Example.** You copy `guard_shell_habits.py` into `.claude/hooks/` and
its self-test passes, but `.claude/settings.json` doesn't name it, so
Claude Code never runs it. The registration check prints
`UNREGISTERED: guard_shell_habits.py is in .claude/hooks but in no
settings file`. One command shows you the gap, before a session relies on
a hook that never runs and someone has to work out why the mistake came
back.

### A document you have to rewrite

`guard_writing_style.py`.

**Without the check.** Claude writes a guide full of phrases that readers
recognize as machine-written: "rest assured", em dashes, sentence after
sentence in the passive voice. You read it, mark the phrases, write the
correction and wait for the rewrite. The rewrite costs another round, and
the same phrases come back in the next document.

**With the check.** The hook reads the text before Claude writes the file.
When it finds such phrases, it refuses the write once and lists each one
with its line number and a suggested fix. Claude rewrites the text in the
same turn, before anyone opens the file.

**Example.** A Write of `docs/setup.md` says "Rest assured, nothing is
lost when you close the window." The hook refuses it and names line 3.
Claude writes "The draft stays in your outbox when you close the window."
You read the guide once and send no corrections. ("How it keeps generated
documents free of LLM-speak" below has the details.)

### A long lessons file read before every task

The "Lessons that apply here" section at the end of each procedure.

**Without the check.** A lessons file grows with every mistake. If Claude
reads all of it before each task, it spends tokens and time on lessons
that have nothing to do with the task. If Claude skips it, it misses the
one lesson that does apply.

**With the check.** Each procedure in the skill ends with a short section,
"Lessons that apply here". It holds one to three lines for each lesson
that matters to that task: what to do instead, and which check enforces
it. Claude reads that short list before it starts the task, and leaves
the rest of the lessons file unread.

**Example.** In this skill, `procedures/spend-less-tokens.md` lists 4 of
the 14 example lessons in `lessons.md`. Before it plans test runs, Claude
reads those 4 entries and then starts the task.

### Other habits in spend-less-tokens.md

`procedures/spend-less-tokens.md` describes more ways to save tokens and
time. These are habits Claude follows, and the skill has no check for
them.

- **Test several changes together.** Example: Claude builds three small
  fixes, each with its own targeted tests. One full run then checks the
  three fixes together before Claude commits them. You wait for one full
  run where there would have been three.
- **Run slow tests only when the files they exercise have changed.**
  Example: a slow test runs a deploy script, and a table ties the test to
  that script. When only a page file has changed, the test run skips that
  test and says why, and you don't wait for it.
- **Restart a killed test run from where it stopped, with fewer workers.**
  Example: a run with 8 parallel workers runs out of memory after 300
  tests have passed. Claude restarts it with 4 workers and runs only the
  tests that had not passed yet, so you wait only for those.
- **Start an agent only for independent or large work.** Example: for a
  one-line fix in a file Claude already has open, Claude makes the edit
  itself. Writing a briefing for an agent and waiting for its report would
  cost more than the edit.
- **Read a large file once, and only the lines you need.** Example: Claude
  searches for the function, reads its lines, and reuses what it learned
  later in the session instead of reading the file again.

## How it keeps generated documents free of LLM-speak

Readers notice phrases that sound machine-written, and you end up
rewriting them by hand. Two templates read Claude's writing before anyone
else does. `guard_writing_style.py` reads documentation files before
Claude writes them, and `reply_checks.py` reads chat replies before you
see them.

### guard_writing_style.py: documentation files

A PreToolUse hook on the Write, Edit and MultiEdit tools. Claude Code runs
a PreToolUse hook before it carries out the tool call, and the hook can
stop the call. This one checks files whose extension is in
`DOC_EXTENSIONS`: `.md`, `.markdown` and `.rst` by default. Add `.txt` if
your plain-text files are documents people read. It skips license files
(`LICENSE`, `LICENSE.md`, `LICENCE.txt` and the like), because their
wording is fixed. For a Write, it checks the whole new content. For an
Edit or MultiEdit, it checks only the new text, so older text already in
the file never counts against an edit.

It catches:

- em dashes, and en dashes used as dashes. An en dash in a range, such as
  pages 10 to 20, passes;
- negative reassurance: "nothing is lost", "nothing happens", "no
  surprises", "rest assured", "pay nothing", "don't worry", and "simply"
  or "just" used to play a step down ("simply run", "just click");
- tell words: "silently", "seamless", "leverage", "delve", "robust",
  "moat", "legible" and "honestly";
- "X, not Y" contrasts, when a text holds 2 or more of them and at least
  one for every 15 sentences (`MIN_CONTRASTS`, `SENTENCES_PER_CONTRAST`).
  The hook lists two in a short note, and lets three in a README of 300
  sentences pass;
- heavy use of the passive voice: a form of "be" or "get" followed by a
  past participle ("is refused", "gets deleted"), in 3 or more sentences
  that make up at least a quarter of all sentences. A step that starts
  with a verb ("Run in a terminal.", "Set to 5 by default.") doesn't count
  as passive. Where the doer really doesn't matter, you can keep a passive
  sentence by sending the same call again.

Before it looks for these patterns, the hook removes text it shouldn't
judge: front matter, fenced and indented code blocks, inline code, URLs,
link targets, HTML tags and comments, block quotes, and text in double
quotes, straight or curly. A fence or comment that never closes runs to
the end of the text. When a quotation holds a quotation of its own, the
hook leaves out the whole outer quotation. For an Edit, the hook reads the
file to see whether the text the Edit replaces sits inside a fenced block
or an HTML comment, and treats the new text the same way. It leaves
quotations alone because documents quote people word for word, and a
quotation keeps the speaker's own words. It does read text in single
quotes, because a single quote is also an apostrophe. It has no check for
aphoristic closing lines ("Small steps, big wins."), because no pattern
can tell them apart from an ordinary short sentence. Keep a rule about
them in the project's `CLAUDE.md` instead.

It reads its input as UTF-8 bytes and writes its answer as UTF-8. Without
that, Python on Windows decodes the input with the console's code page
(cp1252), every em dash and curly quote arrives as different characters,
and the hook misses them. The other hook templates read and write the
same way.

When it finds something, it refuses the call once and lists each hit with
its line number and a fix. If Claude sends the identical call again, the
hook lets it through, so a phrase you keep on purpose costs one resend.
To recognize the repeat, the hook keeps a hash of each refused call in a
small state file. Its log holds one JSON line per call, with each hit's
check, line and matched text, and the call's hash. With a short script,
you can count for each check how many calls it refused and how many Claude
sent again unchanged. Those resends are likely false positives, and a
check with many of them needs narrowing.

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

After the rewrite, the hook lets the write through:

```
# Setup

The draft stays in your outbox when you close the window.
Run the installer.
```

### reply_checks.py: chat replies

A Stop hook, which Claude Code runs each time Claude finishes a reply. Its
`CHECKS` list holds pairs of a pattern and an instruction. When a reply
matches a pattern, the hook holds the reply back once and tells Claude
what to fix. Claude's second attempt always goes through. The template
comes with two checks: a reply that states the current time without
reading the clock, and a reply that says you decided or asked for
something. Add the phrases you find yourself correcting in the same form,
for example:

```python
{
    "name": "negative reassurance",
    "pattern": re.compile(r"\brest assured\b|\bnothing is lost\b|\bno surprises\b", re.I),
    "ask": "Say what happens instead of what does not.",
},
```

With that entry added, suppose a draft reply ends:

```
I moved the settings to the new file. Rest assured, nothing is lost.
```

The hook holds it back once. The reply you read:

```
I moved the settings to the new file. The old file keeps a copy until you delete it.
```

### Adding a project's own phrases

1. In `guard_writing_style.py`, add a pair of a pattern and a fix to the
   list it belongs in: `NEGATIVE_REASSURANCE`, `TELL_WORDS`, `DASHES` or
   `CONTRASTS`. Add file types to `DOC_EXTENSIONS`, and add paths the hook
   must skip (a vendored file, a copied changelog) to `SKIPPED_PATHS`.
2. In `reply_checks.py`, add an entry to `CHECKS` for the same phrase in
   replies.
3. Add two self-test cases for each: a text the hook must refuse, and a
   similar one it must let through. Run
   `python skills/lessons-to-checks/templates/selftests/run_all.py`.
4. Record the correction as a lesson, and list it under the writing-style
   procedure (`procedures/writing-style.md`).

## What is in it

- **The method** (`skills/lessons-to-checks/SKILL.md`):
  1. Record every mistake or correction as a lesson right away: what
     happened, and what would fix it.
  2. Build the fix when you record the lesson, as a check that acts on its
     own: a hook, a test or a commit check. Settle for a written note only
     when no check is possible, and say why.
  3. Before marking a lesson fixed, prove the fix works by seeing it act.
     For a hook, that means a settings file names it and you have seen it
     fire in a session.
  4. Never delete a lesson. Mark it fixed or canceled.
  5. List each lesson under every task procedure it applies to. A test
     fails when a lesson appears in no list.
  6. Use a reply check to hold back, once, a reply that repeats a writing
     habit you corrected.
  7. Have an agent that hasn't seen the work review significant changes
     and designs.
  8. Audit lessons, decisions and checks from time to time.
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
  | `reply_checks.py` | Stop hook that holds back a reply once when a pattern matches; the second attempt goes through |
  | `check_lesson_commit.py` | commit-msg check that refuses a lesson added without a code change (or a `Lesson-fix: none - <why>` line), and a lesson removed |
  | `check_lessons_mapped.py` | Fails for a lesson listed under no procedure |
  | `check_hooks_registered.py` | Fails for a hook script that no settings file names |
  | `guard_test_reruns.py` | PreToolUse hook that refuses a full test run on a tree that already passed one, and a full run after a few failures when only tests or documents changed since; it names the test files to run, and `# full-run-again` in the command lets a needed full run through |
  | `conftest_run_record.py` | A conftest.py snippet that writes the run record `guard_test_reruns.py` reads, at the end of each full pytest run |
  | `guard_agent_prompts.py` | PreToolUse hook on the Agent tool that refuses an agent prompt missing a line its work needs: whether the agent runs the full test suite (for a prompt that builds or changes code), a scratch subfolder of the agent's own, and no request to start another agent; it says which line to add |
  | `guard_writing_style.py` | PreToolUse hook on Write, Edit and MultiEdit that refuses, once, documentation text with em dashes, negative reassurance, tell words, repeated "X, not Y" contrasts or heavy passive voice; it lists each hit with its line and a fix, and the same call sent again passes |
  | `settings-example.json` | Shows how to register the hooks in a settings file |

  Each template has a self-test in `templates/selftests/`. To run them
  all, use `python skills/lessons-to-checks/templates/selftests/run_all.py`;
  the last line reads "ok (all 9 self-tests)". The commit-check and
  test-run self-tests need `git`. The end-to-end part of the run-record
  self-test needs `pytest`, and prints "skip" without it. The hook
  self-tests share `selftests/hook_io.py`. It sends each hook its input as
  raw UTF-8 bytes with Python's UTF-8 mode off, and runs each hook once
  behind a strict cp1252 console, the way Windows runs it.

Installing the plugin adds the skill to your sessions and no hooks. You
choose which templates to copy into a project and register there.

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
   `docs/procedures/`. End each one with a `## Lessons that apply here`
   section. The skill's own procedures are a starting point.
3. **Copy the hooks** you need into `.claude/hooks/` and register them in
   `.claude/settings.json` (`templates/settings-example.json` shows how).
   Use the Python command that works on your machine (`python`, `python3`
   or `py`). For `guard_test_reruns.py`, also copy
   `templates/conftest_run_record.py` into `tests/conftest.py`, and keep
   `logs/` and `.claude/logs/` in `.gitignore`.
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
   and `check_hooks_registered.py --hooks .claude/hooks`. Each prints "ok",
   or names what is wrong.
6. **Tell Claude about it** in the project's `CLAUDE.md`:

   ```
   Lessons are in docs/lessons.md and never deleted. Record each mistake
   or correction there at once and build its check in the same commit
   (the lessons-to-checks skill). Before a task, open its procedure in
   docs/procedures/ and read "Lessons that apply here" first.
   ```

7. **Start a new session and prove each hook fires once**, with a harmless
   input that matches it. Claude Code reads its settings when a session
   starts, so a session that was already open won't run the new hooks.

## A worked example

A script reported that a nightly job ran at 17:01 local time. It actually
ran at 12:01. The shell had no time-zone database, so
`TZ=America/New_York date` printed UTC.

**1. The lesson.** Claude adds it to the top of `docs/lessons.md`:

```
- **2025-01-14, a script stated the wrong time zone.** A report said a job
  ran at 17:01 local time; it ran at 12:01. The shell had no time-zone
  database, so `TZ=America/New_York date` printed UTC. What would implement
  it: a PreToolUse hook that refuses `TZ=` with a named zone and says which
  clock to use instead. Status: open.
```

**2. The check.** Claude adds an entry to `HABITS` in
`.claude/hooks/guard_shell_habits.py` (the template already holds this
one):

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

Its self-test has one command the hook must refuse,
`TZ=America/New_York date`, and a similar one it must let through,
`TZ=UTC date`.

**3. The hook registered.** Until a settings file names the hook, the
registration check says:

```
$ python check_hooks_registered.py
UNREGISTERED: guard_shell_habits.py is in .claude/hooks but in no settings file
```

After Claude adds the `PreToolUse` entry from
`templates/settings-example.json` to `.claude/settings.json`:

```
$ python check_hooks_registered.py
ok (every hook script is registered)
```

**4. The hook refusing, in a new session.** Claude tries to run
`TZ=America/New_York date`. The hook stops the command before it runs and
sends Claude this message:

```
PreToolUse:Bash hook error: Refused (named time zone in TZ=): This shell
has no time-zone database, so a named zone in TZ= is ignored and the time
printed is UTC (lesson: a script stated the wrong time zone). Read the
local time with a tool that honors the zone, such as Python's zoneinfo
with the tzdata package installed.
```

The hook also adds a line to its log, `.claude/logs/guard_shell_habits.log`:

```
2025-01-14 12:00:30	deny	named time zone in TZ=
```

**5. The lesson marked fixed.** Claude changes the entry's status line in
place:

```
Status: fixed 2025-01-14, enforced by .claude/hooks/guard_shell_habits.py
("named time zone in TZ="), seen refusing `TZ=America/New_York date`.
```

**6. The lesson listed** under each procedure it applies to, such as
`docs/procedures/scripts.md`:

```
## Lessons that apply here

- **2025-01-14, a script stated the wrong time zone.** Read the local time
  with a clock that honors zones. Check: the shell-habit guard.
```

**7. One commit** holds the entry, the hook, its self-test, the settings
change and the procedure line. The commit check lets it through, because
a hook changed alongside the lesson. If Claude commits the entry on its
own, the commit check refuses it:

```
commit refused: This commit adds a lesson to docs/lessons.md (a new entry
or a note added to one) but changes no hook, test, script or code. Build
the fix in this commit: a check that refuses the mistake, with its test.
If no check is possible, add the line 'Lesson-fix: none - <why no check
is possible>'.
```

If the mistake happens again, Claude adds a note to the entry ("Again
2025-03-02: ...") and makes the check stronger. The entry stays on record.

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
