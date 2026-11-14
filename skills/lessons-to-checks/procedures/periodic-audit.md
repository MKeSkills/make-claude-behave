# Periodic audit

Checks drift. A decision gets written only in a commit message, a check
fires on ordinary work until someone switches it off, a test stops testing
what it claims to. A monthly audit catches what the day-to-day loop misses.
Keep the date of the last audit in the project's review log, so a session
can see when the next one is due.

## Steps

1. **Lessons.** Read every open lesson. For each: is its check built,
   registered and seen acting? Build or prove what is missing
   (procedures/build-the-check.md, procedures/prove-the-check.md). Run the
   mapping check and the registration check; both print "ok".
2. **Repeats.** Search the lessons for notes ("Again ..."). A lesson that
   repeated after it was marked fixed has a check that does not cover the
   case: strengthen it.
3. **Check cost.** Read each hook's log. For each check: how often did it
   fire, and were the firings real? A check that fires on more than about
   1% of replies or commands, or mostly on ordinary work, is narrowed or
   dropped. Tell the person you work for when a check costs more than it
   catches.
4. **Decisions.** Give the project record (history, notes, code) to
   separate read-only reviewers, with the decisions list to read first.
   Each lists decisions the list lacks, entries that contradict the record
   or the code, and notes that contradict the repository. Check their
   findings, then update the list.
5. **Test quality.** A reviewer who did not write the tests picks the
   riskiest code paths and, for each, checks by mutation that a test fails
   when the behavior breaks (procedures/prove-the-check.md, step 1). A
   surviving mutation becomes a new test, or is explained as harmless.
6. **Record the audit**: the date and what was found, in the review log.

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-04-07, an audit found a decision recorded only in a commit
  message.** Compare the decisions list with the history and code; add each
  missing decision with its source. Check: rule only (no check can tell a
  decision from any other sentence).
- **2025-02-10, a reply check stopped replies that quoted someone else's
  words.** Read each check's firing rate in its log; narrow a check that
  fires on ordinary work. Check: the log written by
  `templates/reply_checks.py`.
