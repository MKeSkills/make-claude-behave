# Lessons

Every mistake, correction or surprise in this project, with the check that
enforces its fix. Entries are never deleted: a fixed one is marked fixed, a
canceled one is marked canceled, and both stay on record.

A lesson is any of these:

- a correction from a person you work for;
- a mistake that reached something real (a commit, a file, a message, a
  record);
- a tool or system that behaved differently than expected;
- a decision a later session would need.

## Format

One entry each. The first line (date and short name, in bold) is the
entry's name: procedures list the lesson by it, and the commit check knows
the entry by it, so keep it unchanged once written.

```
- **YYYY-MM-DD, short name.** What happened, in one or two sentences. What
  would implement the fix: the hook, test, commit check or code change that
  stops it from happening again. Status: open.
```

When the same mistake happens again, add a note to the existing entry
("Again YYYY-MM-DD: ...") and strengthen its check. Do not add a second
entry.

Status lines:

- `Status: open.` The fix is not built or not yet seen acting.
- `Status: fixed YYYY-MM-DD, enforced by <the check, test or rule>.` The fix
  exists where it will be used and was seen acting.
- `Status: canceled YYYY-MM-DD, <who canceled it and why>.`

## Lessons

Newest first. The skill's README has a full worked example of one entry.
