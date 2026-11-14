# Lessons (examples)

These are example lessons, in the format of `templates/lessons-template.md`.
Each one is listed under the procedures it applies to, in their "Lessons that
apply here" sections, and `templates/check_lessons_mapped.py` checks that
(run by `templates/selftests/selftest_check_lessons_mapped.py`). In your own
project, keep your lessons in your own file, such as `docs/lessons.md`.

## Lessons

- **2025-06-02, a guide was written in LLM-speak.** A setup guide Claude
  wrote opened with "Rest assured, nothing is lost", used three em dashes,
  and put most steps in the passive voice. The person rewrote it by hand.
  The reply check reads only chat replies, so no check read the file. What
  would implement it: a PreToolUse hook on Write, Edit and MultiEdit for
  documentation files that refuses these phrases, em dashes and heavy
  passive voice once, listing each hit with its line and a fix. Status:
  fixed 2025-06-02, enforced by templates/guard_writing_style.py, seen
  refusing a Write of "Rest assured, nothing is lost." to a Markdown file.

- **2025-05-19, the whole suite ran again after one test failed.** A full
  run of about 15 minutes failed one test. The fix touched only that test's
  file, and the next step ran the whole suite again: another 15 minutes and
  a large share of the session's tokens, for an answer one file's run gave
  in seconds. What would implement it: the test runner records which tests
  failed and the files as the run saw them, and a PreToolUse hook refuses a
  full run when only test or document files changed since, naming the files
  to run; a `# full-run-again` comment lets a needed full run through.
  Status: fixed 2025-05-19, enforced by templates/guard_test_reruns.py
  ("rerun failed") with templates/conftest_run_record.py, seen refusing
  `pytest` and naming `pytest tests/test_bad.py`.

- **2025-05-12, the full suite ran twice on an unchanged tree.** A session
  ran the full suite, read the result, and ran it again before committing,
  with no file changed in between. The second run gave the same answer.
  What would implement it: the test runner records the tree each passing
  full run ran on (the commit and a hash of every uncommitted change), and
  a PreToolUse hook refuses a full run on the same tree. Status: fixed
  2025-05-12, enforced by templates/guard_test_reruns.py ("same tree") with
  templates/conftest_run_record.py, seen refusing `pytest` after a passing
  run.

- **2025-05-05, every builder agent ran the full suite.** Three agents each
  built one part of a batch, and each ran the full suite on its own part;
  the combined tree then needed a fourth run. One run on the combined tree
  was the only one that counted. What would implement it: every agent
  prompt says whether that agent runs the full suite, and a PreToolUse hook
  on the Agent tool refuses a build prompt that says nothing about it.
  Status: fixed 2025-05-05, enforced by templates/guard_agent_prompts.py
  ("full runs"), seen refusing the prompt "Build the export button and add
  its tests."

- **2025-04-07, an audit found a decision recorded only in a commit
  message.** A later session reversed a deliberate choice, because the reason
  for it was in one commit message and nowhere a session reads before acting.
  What would implement it: the periodic audit compares the decisions list
  with the history and the code, and adds each missing decision with its
  source. Status: fixed 2025-04-07, enforced by the audit checklist in
  procedures/periodic-audit.md (rule only: no check can tell a decision from
  any other sentence in a commit message).

- **2025-03-10, a lesson was listed under no procedure.** A lesson about
  release steps sat in the lessons file only; the next release repeated the
  mistake, because nobody opens the whole lessons file before a release. What
  would implement it: a test that fails for a lesson listed under no
  procedure, and for a listed line that names no lesson. Status: fixed
  2025-03-10, enforced by templates/check_lessons_mapped.py, seen failing
  with "MISSING: ..." before the line was added.

- **2025-03-02, payments were matched to invoices by amount and date.** A
  reconciliation script linked each payment to the invoice with the same
  amount on the same day. Two invoices of the same amount on one day got
  each other's payments. Records are identified only by their ID (the
  invoice number, the payment provider's reference, a database key), never
  matched by time, amount, quantity or other details, and a value a record
  does not carry (a payment with no invoice reference) is reported as
  missing, never inferred. What would implement it: a test with two invoices
  of the same amount on the same day, and a line in every review prompt for
  code that links records. Status: fixed 2025-03-02, enforced by that test,
  seen failing on the old matching code.

- **2025-02-24, a mutation test passed on stale bytecode.** A test was
  checked by putting the bug back (changing `max` to `min`), and the test
  still passed. The edit kept the file's size and timestamp, so Python
  loaded the old compiled file and the bug never ran. What would implement
  it: run mutation tests with `PYTHONDONTWRITEBYTECODE=1` and clear
  `__pycache__` first. Status: fixed 2025-02-24, enforced by
  templates/selftests/run_all.py, which sets PYTHONDONTWRITEBYTECODE.

- **2025-02-17, a review confirmed the author's own theory.** The review
  prompt said what the author believed the bug was. The reviewer agreed and
  missed a second defect in the same change. What would implement it: give
  the reviewer the diff, the code it calls and the project's rules, never
  the author's conclusion, and ask it to try to refute each of its own
  findings. Status: fixed 2025-02-17, enforced by the prompt in
  procedures/independent-review.md (rule only: no check can tell whether a
  prompt carries a conclusion).

- **2025-02-10, a reply check stopped replies that quoted someone else's
  words.** The check for decisions attributed to the person fired on text
  quoted from a document ("you decided to skip it"), on about one reply in
  twelve. What would implement it: leave quoted text, block quotes and code
  out before matching, add a case that must not fire, and read each check's
  firing rate in its log at the periodic audit. Status: fixed 2025-02-10,
  enforced by templates/reply_checks.py (`outside_quotes`) and its
  self-test.

- **2025-02-03, a lesson was marked fixed when only a note had been
  written.** The entry said "fixed" with a rule written in a document, and
  the same mistake happened a week later. What would implement it: a commit
  check that refuses a new lesson with no hook, test, script or code beside
  it, and a rule that a lesson is marked fixed only after its check was seen
  acting. Status: fixed 2025-02-03, enforced by
  templates/check_lesson_commit.py, seen refusing a commit that added an
  entry alone.

- **2025-01-28, a reply stated the current time without reading the
  clock.** A reply said "it is 16:40, too late to deploy today" from a guess; the
  clock said 13:40. What would implement it: a reply check that stops a
  reply stating the current time when no tool call of the turn read the
  clock. Status: fixed 2025-01-28, enforced by templates/reply_checks.py
  ("current time stated with no clock read"), seen stopping a reply.

- **2025-01-20, a hook was built and tested but never registered.** Its
  own tests passed, so it was marked fixed. No settings file listed it, so
  it acted in no session, and the mistake it guarded against happened
  again. What would implement it: a check that every hook script is named in
  a settings file, and seeing the hook act once in a new session. Status:
  fixed 2025-01-20, enforced by templates/check_hooks_registered.py, seen
  reporting "UNREGISTERED: ..." before the settings were changed.

- **2025-01-14, a script stated the wrong time zone.** A report said a job
  ran at 17:01 local time; it ran at 12:01. The shell had no time-zone
  database, so `TZ=America/New_York date` printed UTC. What would implement
  it: a PreToolUse hook that refuses `TZ=` with a named zone and says which
  clock to use instead. Status: fixed 2025-01-14, enforced by
  templates/guard_shell_habits.py ("named time zone in TZ="), seen refusing
  `TZ=America/New_York date`.
