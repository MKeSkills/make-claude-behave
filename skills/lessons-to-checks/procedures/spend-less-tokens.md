# Spend less tokens

Use this when planning tests, batching changes or starting agents. A full
run of a large test suite, an agent started for a small job, or a big file
read twice each costs minutes and a share of the session's token budget.
Most of that cost buys an answer that was already known.

Each step below saves tokens and wall-clock time the same way: it skips a
run, a read or an agent whose answer is already known, so neither the
session nor the person waits for it. For example, a full run refused after
2 failures fixed in test files is replaced by a run of those 2 files, and
the session waits only for those.

## Steps

1. **Batch changes into one test cycle.** Build several changes, each with
   its targeted tests (the tests for the code it touches) and its mutation
   tests (procedures/prove-the-check.md, step 1). Then run the full suite
   once, on the combined tree, before committing them together. Run the full
   suite for a single change only when that change must go out on its own.
2. **Say in every agent prompt whether that agent runs the full suite.** A
   builder agent runs only its targeted and mutation tests and hands its
   changes back. One agent, or the main session, runs the batch's one full
   run. A prompt that says nothing invites each agent to run the whole
   suite. Copy `templates/guard_agent_prompts.py` into `.claude/hooks/` and
   register it (matcher `Agent|Task`, `templates/settings-example.json`). It
   refuses a prompt that asks for code to be built or changed with no line
   on full runs, and says which line to add. It also refuses a prompt that
   names the shared scratch folder without a subfolder of the agent's own,
   and one that asks the agent to start another agent.
3. **Never run the full suite twice on an unchanged tree.** Have the test
   runner record each full run: whether it passed, and the tree it ran on
   (the commit and a hash of every uncommitted change). Copy
   `templates/conftest_run_record.py` into the project's `tests/conftest.py`
   and `templates/guard_test_reruns.py` into `.claude/hooks/`, and register
   the hook (`templates/settings-example.json`). The hook refuses a second
   full run on a tree that already passed one.
4. **After a full run that failed a few tests, rerun only their files.**
   When every file changed since that run is a test file (`test_*.py` or
   `*_test.py`) or a document, program code is as the run saw it. A change
   to `conftest.py`, a shared test helper or test data can change what
   every test sees, so it calls for a full run. Run the failed tests'
   files, each test file changed since, each test file that imports a
   changed one, and each test file that names a changed document. The same
   hook refuses the full run and names the files, for example
   `pytest tests/test_invoices.py`. A comment in the command,
   `# full-run-again`, lets a needed full run through: a dependency
   upgraded, a flaky test, a run asked for by name, or a changed document
   that a test reads through a folder pattern such as `docs/*.md`.
5. **Run slow tests only when the files they exercise changed.** Tie each
   slow test to the files it runs or reads, in a table the test suite
   checks. Keep a record of the file versions (content hashes) each test
   last passed with, one entry per test id. A run skips a slow test whose
   files are all byte for byte as they were when it passed, and says why.
   It runs them all when a file they share changed, when no pass is
   recorded, and on a fixed schedule (for example once a week) to catch
   what the table misses.
6. **Restart a killed run with fewer workers, from where it stopped.** A
   parallel run that ran out of memory is restarted at once with fewer
   workers (for example `-n 4` instead of `-n 8`), and runs only the tests
   that had not passed yet, taken from the killed run's report. Starting
   over repeats every test that already passed.
7. **Start an agent only when the work is independent or large.** Several
   unrelated parts that can run at once, or a search across many files
   whose details you do not need to keep, are worth an agent. A handful of
   tool calls whose target you already know are cheaper done yourself. An
   agent knows only what its prompt says, so a short job handed over often
   costs more in briefing than in doing.
8. **Do not read a big file twice or work out again what is established.**
   Read the part you need, by line range or by search. Note what a file
   said the first time, and reuse a conclusion already reached in the
   session instead of deriving it again.
9. **Fix a lesson when it is recorded.** Each repeat of a mistake costs
   another round: the mistake, the correction, the rework and its test run.
   Build the check the first time (procedures/build-the-check.md).

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-05-19, the whole suite ran again after one test failed.** Rerun
  only the failed tests' files when only tests or documents changed since
  the run; add `# full-run-again` when program code must run in full.
  Check: `templates/guard_test_reruns.py` ("rerun failed").
- **2025-05-12, the full suite ran twice on an unchanged tree.** Record
  each full run with the tree it ran on, and run only targeted tests until
  something changes. Check: `templates/guard_test_reruns.py` ("same tree")
  with `templates/conftest_run_record.py`.
- **2025-05-05, every builder agent ran the full suite.** Say in each
  agent prompt whether that agent runs the full suite; builders run only
  targeted and mutation tests. Check: `templates/guard_agent_prompts.py`
  ("full runs").
- **2025-02-03, a lesson was marked fixed when only a note had been
  written.** Build the check when the lesson is recorded, so the mistake
  does not cost another round. Check: `templates/check_lesson_commit.py`.
