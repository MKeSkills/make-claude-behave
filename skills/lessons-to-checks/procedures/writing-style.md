# Writing style

Use this when Claude writes a document other people read (a README, a
guide, release notes, a letter), or when a person corrects the wording of
one. Some phrases mark text as generated and say little: em dashes,
reassurance phrased as a negative, filler words, and sentence after
sentence in the passive voice. A person who corrects them once expects them
gone from the next document too.

A hook catches these phrases before the file is written. That saves tokens
and time: Claude rewrites the text in the same turn, and the person reads
the document once. Caught by the person, the same phrases cost them reading,
marking and correcting the text, and cost Claude another round.

## Steps

1. **Install the hook.** Copy `templates/guard_writing_style.py` into
   `.claude/hooks/` and register it with the matcher `Write|Edit|MultiEdit`
   (`templates/settings-example.json`). Start a new session and see it
   refuse a harmless Write of a Markdown file holding "Simply run it."
2. **Set what it reads.** It reads `.md`, `.markdown` and `.rst` files by
   default, and never license files. Add the project's other document
   types to `DOC_EXTENSIONS` (`.txt` if plain-text files are documents
   people read), and paths it must never check (a vendored file, a copied
   changelog) to `SKIPPED_PATHS`.
3. **Turn each wording correction into a pattern.** When a person corrects
   a phrase, record the lesson (procedures/record-a-lesson.md) and add the
   phrase to the matching list in the hook: `NEGATIVE_REASSURANCE`,
   `TELL_WORDS`, `DASHES` or `CONTRASTS`, each with a plain fix. Add a
   self-test case that must be refused and a similar one that must pass.
4. **Add the same phrase to the reply check** when it also shows up in chat
   replies: an entry in `CHECKS` in `templates/reply_checks.py`
   (procedures/reply-checks.md).
5. **When the hook refuses a write**, rewrite each listed line with the fix
   it names. Send the identical call again only when every hit is meant: a
   passive where the doer does not matter, or a word the reader needs. Put
   a quotation in double quotes or a block quote, so the hook leaves it
   out.
6. **Read the last line of each section yourself.** The hook has no check
   for aphoristic closing lines ("Small steps, big wins."), because no
   pattern tells them apart from an ordinary short sentence. Keep a rule
   about them in the project's `CLAUDE.md`.
7. **Read its log at the periodic audit**
   (`.claude/logs/guard_writing_style.log`, one JSON line per call): how
   often each check fired, and whether the hits were real. A refusal sent
   again unchanged (a "pass-resent" line with the refusal's hash) is a
   likely false positive. Narrow a pattern that fires on ordinary text.

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-06-02, a guide was written in LLM-speak.** Write what happens, in
  the active voice, with no em dashes or reassurance phrased as a negative.
  Check: `templates/guard_writing_style.py`.
