# Step 4 — Multiple datasets, save-vs-ship split, named connections, admin-added rows

## Context

The biggest architectural change after step 1. Get this one reviewed carefully — it changes the
save semantics in a way that fixes a real bug class (see the "why" below) and moves the app from
"one active dataset" to "datasets coexist forever."

**Why the save-vs-ship split matters**: if "save" just recomputes the target table from *only
the edits in the current request*, then one end user saving after another silently wipes out the
other's earlier corrections (their edits aren't in this request's payload). The fix is to persist
every edit individually, and have publishing recompute the target table from *all* persisted
edits, not just the current request's — see `invariants.md` point 2. If your rebuild is starting
fresh rather than porting an existing single-dataset POC, ask for this split from the start
instead of retrofitting it.

## Prompt

```
Several changes, all related:

1. Datasets should coexist. Right now ingesting new data replaces whatever was there — instead,
   every ingest (xlsx or DB) should create a new, independent dataset alongside any existing
   ones, each with its own rules, target table, and assigned end users. Nothing implicit like
   "the current dataset" — every admin action should take an explicit dataset to act on. An end
   user's view should aggregate across every dataset they have assigned rows in.

2. Split "save" into two separate steps: autosave only persists an end user's edit into the
   app's own storage — it must never touch the target database table. A separate, explicit
   "Ship to DB" action (available to both the end user, for datasets they have rows in, and the
   admin, for any dataset) publishes the dataset's current state — computed from EVERY persisted
   edit across EVERY end user at that moment, not just whoever just clicked ship — into the
   target table.

3. Add named database connections: instead of pasting a raw connection string every time, let an
   operator predefine connections via environment variables, and expose only the connection
   *names* to the admin UI — the actual connection strings should never leave the server or get
   logged.

4. Admins should also be able to add wholly blank rows (no source data) that are assignable and
   flaggable exactly like an ingested row — for cases where a correction needs new data, not
   just a fix to existing data.

5. Add a metadata endpoint per dataset that shows the live input/output column schema — useful
   for an admin or another system to introspect what a dataset looks like without querying the
   raw table directly.
```

## Expect / confirm

- Claude should ask whether "ship" recomputes from all persisted edits or just accepts the
  request's payload — the answer is **all persisted edits**, this is the whole point of the
  split (`invariants.md` point 2).
- It may ask whether an end user can ship a dataset they have zero rows in — reference build's
  answer: **no**, reject it; an admin can ship any dataset regardless of row assignment.
- Confirm named connections are resolved **server-side only** — the client never sees a
  connection string, only names.

## Checklist after this step

- [ ] Ingesting a new dataset never deletes or hides a prior one.
- [ ] Autosave writes only ever hit a "persist edit" function, never a "rebuild target table"
      function.
- [ ] Shipping recomputes from all persisted edits across all end users — verify with a test:
      end user A saves + ships, then end user B saves + ships, and A's earlier correction is
      still present afterward (this is the regression this whole step exists to prevent).
- [ ] `GET` on the connections list returns names only, never the underlying connection string.
- [ ] Admin-added blank rows are assignable/flaggable through the exact same paths as ingested
      rows.
