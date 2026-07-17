# Step 3 — Custom columns, autosave, search

## Context

Three independent features that tend to get requested together once real users start using the
POC. They're independent enough to split into separate prompts if you want to review each one on
its own — bundled here because that's how they came up in the reference build.

## Prompt

```
Three additions to the admin/end-user flow:

1. Admins should be able to add wholly new columns that don't exist in the source data — e.g. a
   blank "Reviewer notes" column. Each new column is typed as either a fixed dropdown (admin
   defines the options) or free text (with a reasonable max length). Unlike the ingested
   columns, a custom column doesn't need the admin to flag individual cells — every row
   assigned to an end user should get an editable cell in that column automatically.

2. End-user edits should autosave as they type/select, not require a manual "Save" click. Debounce
   free-text fields so we're not firing a request per keystroke. Show an inline per-cell status
   ("Saving…" / "Saved" / an error) so one failing cell's status doesn't get confused with
   another's.

3. Add a search box above both the admin's raw-data table and the end-user's grid that filters
   visible rows by substring match, client-side (no need for a server round-trip at this scale).
```

## Expect / confirm

- Claude should clarify whether custom columns go through the *same* per-cell flagging mechanism
  as ingested columns, or a separate one. Reference build's answer: **separate** — custom
  columns are always-editable by column, not per-cell-flagged (see `invariants.md` point 6).
  This keeps "does this need a rule row per cell" from applying to a column the admin explicitly
  created to be filled in.
- Confirm autosave should call the *exact same* validation path a manual save would (ownership,
  editability, value-in-options) — it's a UI change in when the request fires, not a new,
  looser code path. See `invariants.md` point 7.

## Checklist after this step

- [ ] Admin can create a dropdown or free-text custom column; it appears automatically for every
      assigned row without a separate per-cell flag.
- [ ] End-user edits save without a manual click; per-cell status shows saving/saved/error
      independently per cell.
- [ ] Search boxes filter both tables client-side.
- [ ] Autosave and any pre-existing manual-save path hit the same backend validation function.
