# Step 2 — Bulk row assignment

## Context

A UX convenience on top of step 1's single-row assignment — assigning rows to end users one at a
time doesn't scale past a handful of rows. This step doesn't change the data model (still one
row → one end user), just how many rows an admin can assign in one action.

## Prompt

```
Admins need a way to assign multiple rows to an end user at once, not just one row at a time.
Add a multi-select (checkboxes) on the admin's raw-data table, plus a "share selected rows
with [end user]" action that assigns all of them in one call.

This should use the same underlying single-owner-per-row assignment as the existing per-row
"assign" control — it's a bulk UX on top of the same data model, not a new one. A row still has
exactly one assigned end user; bulk-assigning to a different end user reassigns it, it doesn't
add a second owner.
```

## Expect / confirm

- Claude may ask whether bulk-assigning should *replace* an existing assignment or fail if any
  selected row is already assigned — reference build's answer: **replace silently**, since
  reassignment is a normal admin action, not an error case. State your preference if different.
- It should reuse the existing single-row assignment's backend logic/endpoint pattern rather than
  writing a parallel one — call this out if it starts duplicating logic.

## Checklist after this step

- [ ] Admin table has row checkboxes and a bulk "share with" control.
- [ ] Bulk assignment writes to the exact same field/column the single-row assignment does.
- [ ] A test covers bulk-assigning rows that already had a different owner (reassignment, not a
      second owner).
