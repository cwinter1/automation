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
- `tests/test_target_save.py` — the merge/save logic in isolation: ownership rejection,
  unflagged-cell rejection, out-of-options rejection, malicious `table_name` rejection with **no
  DDL executed**, and `test_cross_enduser_saves_accumulate_without_clobbering` — the single most
  important test in the suite (see Invariant #2 in `CLAUDE.md`).
- `tests/test_auth.py` — admin vs. end-user role isolation, redirect-vs-403 behavior.
- `tests/test_admin_api.py` — exposed-column bounds (4–6), cell-rule validation, single-row and
  bulk-row assignment, admin-added column create/delete/validation.
- `tests/test_review_flow.py` — full integration: ingest → configure → two end users each save
  their own rows → target table has both; also covers admin-added dropdown/text columns being
  always-editable in the grid and their save-side validation (option membership, 500-char cap).

### 2. Manual golden-path check (do this for any UI-touching change)

```bash
export ADMIN_PASSWORD=admin123 SESSION_SECRET_KEY=devsecret
uvicorn app.main:app --reload
```

Then, either by hand in a browser or via `curl` with a cookie jar per role:

1. Log in as admin, ingest a small `.xlsx` (5+ columns, several rows).
2. Expose 4–6 columns, set a target table name.
3. Create two end users. Assign a couple of rows to each — try both the single-row "Assign to"
   dropdown *and* the multi-select "Share selected rows with" bulk action, to cover both paths.
4. Flag at least one cell per end user's rows with 2+ dropdown options.
5. Log in as end user A: confirm the grid shows **only** A's rows, flagged cells are dropdowns,
   everything else is plain text. Save a correction.
6. Query the target table directly (e.g. via a short Python `sqlite3` snippet — there's no
   `sqlite3` CLI in this environment) and confirm A's correction landed and untouched rows
   carried through raw.
7. **Attempt a tamper**: as A, try to submit an edit for a row assigned to B. Confirm it's
   rejected with 422 and the target table is unchanged.
8. Log in as end user B, save a correction, and re-query the target table — confirm B's
   correction landed **and A's earlier correction is still there**. This is the regression this
   whole design guards against; if it silently reverts, something reintroduced the
   request-only-edits bug (see Invariant #2 in `CLAUDE.md`).
9. If the change touched ingestion, also exercise the DB-connector path against a scratch
   SQLite table, not just xlsx.
10. Add a dropdown-type and a text-type custom column ("4. Custom columns"). Confirm both show
    up immediately in an assigned end user's grid as editable — without touching the exposed-
    columns checkboxes — and that an out-of-options dropdown value or an over-500-character text
    value gets rejected with 422.
11. On the end-user grid, change a cell's value and confirm it saves **without** clicking Save
    (watch for the inline "Saving…" → "Saved" text next to the cell), then re-query the target
    table to confirm it actually persisted. Also confirm the manual Save button still works as a
    fallback.
12. Type into the search box on both the admin raw table and the end-user grid and confirm rows
    not matching the search term are hidden (client-side only — no network request should fire).

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
