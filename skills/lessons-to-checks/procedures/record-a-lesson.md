# Record a lesson

Use this the moment something goes wrong: a correction from the person you
work for, a mistake that reached something real (a commit, a file, a
message, a record), a tool or system that behaved differently than
expected, or a decision a later session would need. Record it now, without
asking and without waiting for the end of the work. A lesson that waits is
lost when the session runs out of room.

## Steps

1. **Read the clock** for the entry's date. Do not take it from memory or
   from a UTC timestamp in a log.
2. **Search the lessons file for the same mistake.** If an entry exists, add
   a note to it ("Again YYYY-MM-DD: what happened this time") and go to
   step 5: a repeat means the existing check was too weak or missing.
3. **Write a new entry** at the top of the lessons file, in the format of
   `templates/lessons-template.md`:

   ```
   - **YYYY-MM-DD, short name.** What happened, in one or two sentences.
     What would implement the fix. Status: open.
   ```

   The short name says what went wrong in plain words ("a hook was built
   and tested but never registered"). It is the lesson's name everywhere
   else, so do not change it later.
4. **Say what happened concretely**: the command, the file, the message,
   and what the person saw. "A mistake with time zones" is not enough;
   "a report said 17:01 local time; it was 12:01" is.
5. **Build the fix now** (procedures/build-the-check.md). The lesson and
   its check go in the same commit.
6. **List the lesson under every procedure it applies to**
   (procedures/map-lessons-to-tasks.md), in the same commit.
7. **Commit the entry, the check and the listing together.** The commit
   check (`templates/check_lesson_commit.py`) refuses a commit that adds a
   lesson with no hook, test, script or code beside it. Only when no check
   is possible, add a line to the commit message saying why:
   `Lesson-fix: none - <why no check is possible>`.
8. **When the work wraps up, say which lessons were recorded**, in one
   line: "Recorded 2 lessons: X; Y."

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-03-10, a lesson was listed under no procedure.** List each new
  lesson under every procedure it applies to, in the same commit. Check:
  `templates/check_lessons_mapped.py`.
- **2025-02-03, a lesson was marked fixed when only a note had been
  written.** Record the lesson with its check in one commit; a note alone
  needs a `Lesson-fix: none - <why>` line. Check:
  `templates/check_lesson_commit.py`.
