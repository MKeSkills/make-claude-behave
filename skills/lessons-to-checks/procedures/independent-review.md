# Independent review

Code and tests written from one line of reasoning share its mistakes. A
reviewer that has not seen the work reads it fresh. There are two kinds.

**Code review**, before committing a significant change: new or changed
logic, an endpoint, a screen's behavior, data or schema, or anything that
touches money, accounts, keys, access or sign-in. Not needed for
documentation, wording, settings or renames alone. When unsure, review.

**Design review**, before building a significant new feature: a new screen
or section, a new kind of data, a new scheduled job, or a change to what
users are shown. Design mistakes found after the build cost a rebuild.

## Steps

1. **For a design review, write the design down first**: what each part
   does, what it shows, the exact wording users will see, what it changes,
   and what it rests on in the code and the recorded decisions. Mark
   anything unverified.
2. **Start a separate agent** that has not seen the conversation. Give it:
   - the diff and the code it calls (code review), or the written design
     (design review);
   - the project's recorded decisions and rules, to check against;
   - read-only access, and the instruction to try to refute each of its own
     findings before reporting.
   Do not give it your own theory of what is wrong. It will tend to confirm
   it.
3. **If the change links records** (orders, payments, transactions, users),
   add this line to the prompt: records are identified only by their ID (an
   order id, an invoice number, a database key), never matched by time,
   amount, quantity or other details, and a value a record does not carry
   is never inferred.
4. **Check every finding against the code** before fixing anything. A
   reviewer's finding is a claim too.
5. **Fix and test** confirmed findings like any other change. A finding
   whose fix changes what users can do, or a decision that belongs to the
   person you work for, goes to that person first.
6. **Record the review**: in the commit message, a line saying what the
   review found (`Review: <findings>`) or why none was needed
   (`Review: none - <reason>`); and a line in the project's review log.
7. **A mistake the review caught that a check could have caught** becomes a
   lesson (procedures/record-a-lesson.md).

## Lessons that apply here

Each line names a lesson in `lessons.md` by its date and short name, says
what to do instead, and names the check that enforces it.

- **2025-03-02, payments were matched to invoices by amount and date.**
  Identify records only by their ID, never by time, amount or quantity, and
  report a missing value instead of inferring it; say so in every review
  prompt for code that links records. Check: a test with two invoices of
  the same amount on one day.
- **2025-02-17, a review confirmed the author's own theory.** Give the
  reviewer the diff and the rules, never your conclusion, and ask it to
  refute its own findings. Check: rule only (no check can tell whether a
  prompt carries a conclusion).
