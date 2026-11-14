# Build the check

Use this right after recording a lesson, or when a lesson's check turned out
too weak. Build the fix when you record the lesson, before the mistake can
repeat.

A check built now saves tokens and time on every later occurrence. The
mistake is refused at once, which skips the round spent making it, working
out its cause again, correcting it and testing the rework. For example, a
refused `TZ=America/New_York date` costs one short refusal. Run unchecked,
it would cost a wrong time in a report and the search for why.

## Steps

1. **Pick the strongest form that can work**, in this order:
   - **A check that blocks the mistake.** A PreToolUse hook that refuses a
     command, a test that fails, a commit check that refuses the commit, or
     a Stop hook that stops a reply (procedures/reply-checks.md).
   - **A rule in a file every session loads** (the project's `CLAUDE.md`),
     only when nothing can recognize the mistake from the outside.
   - **A note in a document**, only when neither is possible. Say why no
     check is possible, in the entry and in the commit message.
   A rule that has been broken once already needs a check, not a second
   note.
2. **Match the check to where the mistake shows**:
   - in a command Claude runs: a PreToolUse hook
     (`templates/guard_shell_habits.py`, add an entry to `HABITS`);
   - in what goes into the repository: a test, or a commit check
     (`templates/check_lesson_commit.py` shows the form);
   - in a reply: a reply check (`templates/reply_checks.py`, add an entry
     to `CHECKS`);
   - in program behavior: a test that fails on the old behavior.
3. **Keep the check narrow.** It refuses the mistake and lets ordinary
   work through. A check that fires on routine work gets switched off, and
   then it protects nothing. Write one case that must be refused and one
   similar case that must pass.
4. **Make its message say what to do instead**, so the next attempt can
   succeed: "Refused (named time zone in TZ=): ... Use Python's zoneinfo
   with tzdata installed."
5. **Make a fault in the check let work through.** A hook that crashes
   must not block every command; log the error instead.
6. **Log each time it acts** (time, outcome, which check), so its firing
   rate can be read at the periodic audit.
7. **Register it.** A hook does nothing until a settings file names it
   (`templates/settings-example.json`). Add the hook's entry to the
   project's `.claude/settings.json`, then run
   `templates/check_hooks_registered.py`; it must print "ok".
8. **Go on to prove it** (procedures/prove-the-check.md).

If the check touches records (orders, payments, transactions, users), it
identifies them only by their ID (an order id, an invoice number, a
database key), never by matching time, amount, quantity or other details,
and it never infers a value a record does not carry.

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-01-20, a hook was built and tested but never registered.**
  Register the hook in a settings file and run the registration check.
  Check: `templates/check_hooks_registered.py`.
- **2025-01-14, a script stated the wrong time zone.** A habit that went
  wrong in a command gets a PreToolUse hook that refuses it and names the
  right tool. Check: `templates/guard_shell_habits.py`.
