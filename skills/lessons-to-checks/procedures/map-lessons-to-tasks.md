# Map lessons to tasks

A lessons file is read when someone thinks to read it, which is rarely at
the moment a lesson matters. Each kind of task gets a procedure file (a
short list of steps), and each procedure ends with the lessons that apply
to it. A session reads that section before doing the task.

This saves tokens and time: before a task, the session reads the few lines
that apply to it instead of the whole lessons file. The lesson that applies
is read at the moment it matters, so its mistake is avoided before it costs
another round to make, diagnose and fix.

## Steps

1. **Keep one procedure per kind of task** the project repeats: a release,
   a code review, a commit message, a reply to the person, a data change.
   Each is a Markdown file of numbered steps in one folder (for example
   `docs/procedures/`).
2. **End each procedure with this section**, exactly:

   ```
   ## Lessons that apply here
   ```

   A procedure with no lessons yet still has the section.
3. **List each lesson under every procedure it applies to**, one line
   each, opening with the lesson's date and short name in bold, exactly as
   the lesson's first line gives them:

   ```
   - **2025-01-14, a script stated the wrong time zone.** What to do
     instead. Check: the shell-habit guard.
   ```

   Then say what to do instead of the mistake, and name the check that
   enforces it, or "rule only" with the reason. Keep each line to one to
   three lines.
4. **Run the mapping check**:

   ```
   python check_lessons_mapped.py --lessons docs/lessons.md --procedures docs/procedures
   ```

   It prints "ok", or "MISSING: <lesson>" for a lesson listed nowhere and
   "UNKNOWN: <procedure>: <name>" for a line naming no lesson. Run it in
   the test suite too, so a commit that adds a lesson without listing it
   fails.
5. **When a new kind of task appears**, add a procedure for it and move the
   lessons that apply into its section.
6. **Point the project's `CLAUDE.md` at the procedures**, with one line:
   before a task, open its procedure and read its "Lessons that apply here"
   first.

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-03-10, a lesson was listed under no procedure.** Run the mapping
  check in the test suite, so a lesson listed nowhere fails the build.
  Check: `templates/check_lessons_mapped.py`.
