# Step 1 — Initial POC

## Context

The seed prompt. Everything else in this playbook builds on the architecture decided here, so
it's worth answering Claude's clarifying questions deliberately rather than rushing through them
— the row/cell-granularity decision in particular is expensive to change later.

## Prompt

```
I need a proof-of-concept web app for a data-correction workflow:

1. An admin ingests source data — either uploading an .xlsx file, or pulling a table from an
   external database via a connector.
2. The admin reviews the raw data, picks a handful of columns to expose to end users, and flags
   specific cells that need a human correction — each flagged cell gets its own dropdown of
   valid replacement values (not a free-text field, not a shared per-column list).
3. End users log in and see only the rows assigned to them. Anything not flagged is locked/
   read-only; flagged cells are dropdowns. They correct their assigned cells and save.
4. Corrected data is written into a new/target database table.

Stack: [Python/FastAPI/SQLAlchemy/SQLite + server-rendered templates + vanilla JS, no build
step — OR say your company's mandated stack here instead].

Ask me one question at a time about anything ambiguous before you start building — I'd rather
answer several short questions than have you guess.
```

## Expect / confirm

Claude will likely ask, one at a time:

- **Ingestion modes** — confirm you want *both* xlsx upload and a DB-connector pull, not just one.
- **Rule granularity** — confirm cell-level flagging (a specific row+column), not column-level.
  This is the decision that's expensive to change later — a per-column rule can't express "only
  this one row's Status field needs correcting," which per-cell can.
- **Which rows an end user sees** — confirm: *only rows explicitly assigned to them*, not
  everything, not a shared queue.
- **Auth** — for the POC, a simple shared password per role (admin / end user) is enough; don't
  build a full user directory yet, that's step 5.
- **Scope for "later"** — tell Claude explicitly that multiple concurrent datasets, a real admin
  directory, and per-user login are *future work*, not in scope for this first pass, but that
  the schema shouldn't preclude them. This keeps step 1 from over-building before you've seen
  the shape of the thing.

## Checklist after this step

- [ ] Ingestion works for both xlsx and DB pull, converging on the same internal row shape.
- [ ] Admin can flag individual cells with a custom dropdown of valid values.
- [ ] End users see only rows assigned to them; corrections save to a target table.
- [ ] A test suite exists and passes, including a test that a malicious table/column name is
      rejected before touching the database (identifier-injection defense — see `invariants.md`
      point 5).
- [ ] `CLAUDE.md` (or your project's equivalent) documents the architecture and has
      `invariants.md`'s contents pasted in.
