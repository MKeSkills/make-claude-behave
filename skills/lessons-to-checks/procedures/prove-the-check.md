# Prove the check, then mark the lesson fixed

Use this after building a check, and before writing "fixed" on any lesson.
A check that was never seen acting may not act at all.

## Steps

1. **See the check fail on the old behavior.**
   - A hook: send it a harmless input that matches it and see it refuse.
     For a shell guard, a command such as `TZ=America/New_York date`, which
     changes nothing if it does run.
   - A test: put the bug back on purpose (a mutation), run the test, see
     it fail, then restore the file from a copy. Run with
     `PYTHONDONTWRITEBYTECODE=1` and clear `__pycache__` first, or Python
     may run the old compiled file and the test passes for the wrong
     reason.
   - A commit check: make a commit it must refuse, in a throwaway
     repository (`templates/selftests/selftest_check_lesson_commit.py`
     does this).
2. **See it pass the similar case it must allow.**
3. **For a hook, see it fire in a real session.** Its self-test proves the
   script works; only a session proves Claude Code runs it. Settings are
   read when a session starts, so start a new session (or open `/hooks`),
   then send the harmless matching input through Claude Code itself and
   see the refusal or the stopped reply.
4. **Run the registration check**: `templates/check_hooks_registered.py`
   prints "ok".
5. **Mark the lesson fixed**, in place:
   `Status: fixed YYYY-MM-DD, enforced by <the check>, seen <what was seen>`.
   Leave the entry where it is. Never delete a lesson.
6. **Say in the reply which check now enforces it and what was seen when it
   acted.** "Fixed" without that is a claim, not a proof.
7. If the person you work for cancels a lesson instead, write
   `Status: canceled YYYY-MM-DD, <who canceled it and why>` and keep the
   entry.

A rule with nothing that can act on it counts as a fix only when no check
is possible. Say why in the status line.

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-02-24, a mutation test passed on stale bytecode.** Run mutation
  tests with `PYTHONDONTWRITEBYTECODE=1` after clearing `__pycache__`.
  Check: `templates/selftests/run_all.py` sets it.
- **2025-02-03, a lesson was marked fixed when only a note had been
  written.** Mark fixed only after the check was seen acting, and say what
  was seen. Check: `templates/check_lesson_commit.py`.
- **2025-01-20, a hook was built and tested but never registered.** A
  passing self-test is not enough; register the hook and see it fire in a
  new session. Check: `templates/check_hooks_registered.py`.
