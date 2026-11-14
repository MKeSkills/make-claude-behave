# Reply checks

Some mistakes live in what Claude says, not in what it runs or commits: a
time stated from a guess, a decision attributed to someone who never made
it, a word the person asked you to stop using. A reply check is a Stop
hook that reads each reply before the person sees it and stops it once
when a pattern matches.

## How it acts

Each check is a pattern and an instruction. When a pattern matches, the
hook stops the reply and tells Claude what to verify. Claude verifies, then
rewrites the reply or confirms it. Claude Code marks that second attempt
(`stop_hook_active`), and the hook lets it through, so it can never loop.
The check is only as good as that verification.

This saves tokens and time: a reply caught before it goes out costs one
rewrite inside the same turn. Caught by the person, it costs them reading
it, writing the correction and waiting for the rewrite, and it costs Claude
another round.

## Steps

1. **Use it for a writing mistake that has happened once** and that
   wording can recognize. A mistake that wording cannot recognize stays a
   rule in the project's `CLAUDE.md`.
2. **Add an entry to `CHECKS`** in `templates/reply_checks.py`: a `name`,
   a `pattern`, and an `ask` that says what to verify. Narrow it with
   `unless` (the reply names its source) or `unless_tools` (a tool call of
   the turn already did the check, such as reading the clock).
3. **Leave quoted text out.** The template removes double-quoted spans,
   block quotes and code before matching, so wording quoted from a document
   or proposed for someone else does not set a check off.
4. **Add two cases to the self-test**: a reply that must be stopped, and a
   similar one that must pass.
5. **Replay it on past replies** if the project keeps transcripts: count
   how many replies it would have stopped. A check that fires on more than
   about 1% of replies, or mostly on ordinary work, is narrowed or dropped.
6. **Register it** as a `Stop` hook (`templates/settings-example.json`),
   start a new session, and see it stop one reply.
7. **Read its log at the periodic audit**: how often each check fired, and
   whether the firings were real.

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-02-10, a reply check stopped replies that quoted someone else's
  words.** Leave quoted text out before matching, and add a case that must
  not fire. Check: `templates/reply_checks.py` and its self-test.
- **2025-01-28, a reply stated the current time without reading the
  clock.** Read the clock in the same turn before stating a time. Check:
  `templates/reply_checks.py` ("current time stated with no clock read").
