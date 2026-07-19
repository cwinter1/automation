---
name: qa
description: How to verify a change to the data-ingestion POC actually works — the pytest suite plus the manual golden-path check, including the cross-end-user save-accumulation guarantee that's easy to silently break.
origin: project
---

# QA for the Data Ingestion + Correction Rules POC

## When to Activate

- Before calling any change to `app/` done, especially to `app/ingestion.py`,
  `app/target.py`, `app/sanitize.py`, or the auth/ownership checks in the routers.
- After modifying anything in `app/templates/` or `app/static/app.js` — the JS has no build
  step and no type checking, so a typo only shows up by actually loading the page.
- Before merging a PR that touches row/cell assignment or the save flow.

## How It Works

### 1. Automated: pytest

```bash
source .venv/bin/activate && pytest -q
```

Every test file maps to a specific risk area — when adding a test, put it in the matching file
rather than creating a new one for a one-off case:

- `tests/test_sanitize.py` — identifier validation, including injection-style inputs
  (`"x; DROP TABLE users;--"`, leading digits, quotes). This is the most security-relevant file
  in the suite; a change here deserves the most scrutiny.
- `tests/test_ingestion_xlsx.py` / `test_ingestion_db.py` — parsing round-trips, blank-row/
  blank-header handling, and (for the DB path) that a connection string never leaks into an
  error message.
- `tests/test_target_save.py` — `apply_enduser_edits` and `ship_dataset_to_db` in isolation
  (kept as two separate functions — see Invariant #2 in `CLAUDE.md`): ownership rejection,
  unflagged-cell rejection, out-of-options rejection, malicious `table_name` rejection with **no
  DDL executed**, persisting without shipping, and
  `test_cross_enduser_saves_accumulate_without_clobbering` — the single most important test in
  the suite.
- `tests/test_auth.py` — three-tier role isolation (`master_admin` / named `admin` / `enduser`),
  redirect-vs-403 behavior, and that only `master_admin` can reach `/admin/admins`.
- `tests/test_admin_api.py` — dataset isolation (ingesting doesn't wipe a prior dataset, a
  column id from one dataset is rejected against another), exposed-column bounds (4–6),
  cell-rule validation, single-row and bulk-row assignment, admin-added column and admin-added
  row create/delete/validation, the metadata endpoint, the ship endpoint, and the
  db-connections-names-only endpoint.
- `tests/test_review_flow.py` — full integration: ingest → configure → an end user saves
  (persists only) → explicitly ships → target table has it; a second end user's ship
  accumulates on top without clobbering; an end user with rows in two datasets sees both in
  `GET /review/grid`; a ship attempt for a dataset the caller has no rows in is rejected (403);
  admin-added dropdown/text columns are always-editable in the grid with their own validation
  (option membership, 500-char cap).

### 2. Manual golden-path check (do this for any UI-touching change)

```bash
export ADMIN_PASSWORD=admin123 SESSION_SECRET_KEY=devsecret
uvicorn app.main:app --reload
```

Then, either by hand in a browser or via `curl` with a cookie jar per role:

0. Log in as master admin (password only), create a named admin account, and confirm that
   account can log in and do everything an admin can (ingest, configure, ship) but gets 403 on
   `/admin/admins` — only the master admin can manage admin accounts. Confirm the "0. Admins"
   section in `admin.html` is visible for the master admin and absent for a named admin.
1. Log in as admin, ingest a small `.xlsx` (5+ columns, several rows) with a label. Ingest a
   **second**, different `.xlsx` with a different label. Confirm both appear in the dataset
   picker/`GET /admin/datasets` and the first is still fully intact — ingesting the second must
   not have wiped or altered it.
2. Select the first dataset. Expose 4–6 columns, set a target table name.
3. Create two end users. Assign a couple of rows to each — try both the single-row "Assign to"
   dropdown *and* the multi-select "Share selected rows with" bulk action, to cover both paths.
4. Flag at least one cell per end user's rows with 2+ dropdown options. Add a blank admin row
   ("Add blank row") and confirm it appears with no source values and can be assigned/flagged
   like any other row.
5. Log in as end user A: confirm the grid shows **only** A's rows (across whichever dataset(s)
   A has rows in), flagged cells are dropdowns, everything else is plain text.
6. Change a cell's value and confirm it autosaves (inline "Saving…" → "Saved") **without**
   clicking anything else. Confirm the target table does **not** exist/update yet — autosave
   only persists, it never publishes (query `sqlite_master` or the target table directly; there's
   no `sqlite3` CLI in this environment, use a short Python `sqlite3` snippet).
7. Click that dataset's "Ship to DB" button. Confirm the target table now exists with A's
   correction and untouched rows carried through raw.
8. **Attempt a tamper**: as A, try to submit an edit for a row assigned to B. Confirm it's
   rejected with 422 and the target table is unchanged.
9. Log in as end user B, save a correction (autosave), ship B's dataset, and re-query the
   target table — confirm B's correction landed **and A's earlier correction is still there**.
   This is the regression this whole design guards against; if it silently reverts, something
   reintroduced the edits-and-publish-in-one-call bug (see Invariant #2 in `CLAUDE.md`).
10. **Ship isolation**: confirm a third end user with no rows in that dataset gets 403 trying to
    ship it, and that the admin can always ship any dataset via `POST
    /admin/datasets/{id}/ship` regardless of who's assigned what.
11. If the change touched ingestion, exercise the DB-connector path: set a `DB_CONN_<NAME>` env
    var pointing at a scratch SQLite table, confirm it appears (name only, never the connection
    string) in the admin's named-connection dropdown / `GET /admin/db-connections`, and that
    ingesting via that name works alongside a raw pasted connection string.
12. Add a dropdown-type and a text-type custom column ("Custom columns"). Confirm both show up
    immediately in an assigned end user's grid as editable — without touching the exposed-
    columns checkboxes — and that an out-of-options dropdown value or an over-500-character text
    value gets rejected with 422.
13. Type into the search box on both the admin raw table and the end-user grid (which may have
    multiple dataset sections) and confirm rows not matching the search term are hidden
    (client-side only — no network request should fire).
14. Check the metadata view (`GET /admin/datasets/{id}/metadata`) reflects the current input and
    output columns for the selected dataset, including any custom columns/rows just added.

### 3. Browser check for template/JS/CSS changes

Playwright with the pre-installed Chromium is available
(`executablePath: "/opt/pw-browsers/chromium"`). Screenshot `/admin` and `/review` after logging
in (cookies can be set directly via `context.add_cookies` — note curl's cookie jar marks
session cookies `#HttpOnly_`, which must be stripped, not skipped, when parsing the jar).

## Examples

- A PR that only changes `app/target.py`'s merge logic: run pytest, focus on
  `test_target_save.py` and `test_review_flow.py`, no browser check needed unless the API
  response shape changed.
- A PR that adds a new admin UI control (e.g. bulk actions): full manual golden-path pass,
  including a Playwright screenshot of the admin page showing the new control in a real
  rendered state, not just "the JS didn't throw."
