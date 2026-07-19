# CLAUDE.md

Guidance for Claude Code sessions working on this product. For the product spec, roles, and
roadmap, see `project.md`. For run instructions and known POC limitations, see `README.md`. For
how this product fits into the wider `automation` builder repo, see `../../CLAUDE.md`.

## Project overview

A FastAPI proof-of-concept: admins ingest data (xlsx upload or a generic DB-connector pull),
define which columns/cells end users may see and correct, and end users make constrained
corrections (dropdowns, not free text). Edits autosave into the app immediately; nothing reaches
the target database table until someone explicitly ships it. Multiple datasets coexist — each
gets its own rules, target table, and assigned end users; an end user's grid spans every dataset
they have rows in.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export ADMIN_PASSWORD=changeme SESSION_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
uvicorn app.main:app --reload   # http://localhost:8000/login

pytest   # full test suite
```

Run these commands from this directory (`products/data-ingestion-correction-poc/`) —
`app`, `tests`, and `pytest.ini` are all siblings here, not at the repo root.

## Architecture

- `app/models.py` — SQLAlchemy models: `Dataset` (has `label`; datasets coexist, nothing wipes
  a prior one), `ColumnDef`, `RawRow`, `ExposedColumn`, `CellEditRule`, `CellEditValue`,
  `TargetTableSetting`, `EndUser`. `ColumnDef` doubles as both an ingested source column and an
  admin-created blank column (`is_admin_added`, `input_type`, `options`) — see Invariant #6.
  `RawRow.is_admin_added` marks a blank row the admin added directly (no source data).
- `app/ingestion.py` — xlsx parsing and DB-connector pulling, both converging on
  `(columns, rows)`; `make_safe_identifier` for deriving safe SQL column names;
  `create_new_dataset` inserts a new `Dataset` alongside any existing ones.
- `app/connections.py` — named DB connections from `DB_CONN_<NAME>` env vars
  (`get_connection_names` for the client-safe name list, `resolve_connection` for the actual
  lookup used only server-side during ingestion).
- `app/sanitize.py` — `validate_identifier`, the one function every dynamically-built SQL
  identifier must pass through. See Invariants below.
- `app/auth.py` — three roles: `master_admin` (the shared `ADMIN_PASSWORD`, no DB row),
  `admin` (a named `AdminUser` account, username/password, created by the master admin),
  `enduser` (per-end-user username/password). `master_admin` and `admin` both get full admin
  access via `require_admin(_page)`; only `master_admin` passes `require_master_admin(_page)`,
  which gates admin-account management. Session-cookie based.
- `app/target.py` — `apply_enduser_edits` (persist only) and `ship_dataset_to_db` (publish to
  the target table) are two separate, independently-callable steps — see Invariant #2.
- `app/routers/admin.py`, `app/routers/review.py`, `app/routers/auth_router.py` — the three
  route groups (admin API/page, end-user API/page, login/logout). Every dataset-scoped admin
  route is `/admin/datasets/{dataset_id}/...`; there is no implicit "current dataset."
- `app/templates/`, `app/static/` — Jinja2 templates + vanilla JS/CSS, no build step.
- `tests/` — pytest; `conftest.py` sets up an isolated temp SQLite DB per test.

## Invariants — do not regress these

1. **SQL identifiers are never string-interpolated without `validate_identifier()` first.** The
   target table name and every column safe-name are used in dynamically generated DDL/DML.
   Values always go through SQLAlchemy bound parameters; identifiers never do (they can't be
   parameterized), so they're checked against `IDENTIFIER_RE` instead. Any new code path that
   builds a table/column name from admin input must call `validate_identifier` first.
2. **Autosave (persist) and Ship (publish) are two separate steps that must stay separate.**
   `apply_enduser_edits` only upserts `CellEditValue` rows — it never touches the target table.
   `ship_dataset_to_db` rebuilds the target table from *all* persisted `CellEditValue` rows
   across every end user, not just the caller's own edits. This is what lets two different end
   users ship independently without one wiping out the other's earlier corrections. Do not merge
   these back into one "save and publish" call — that reintroduces the clobbering bug this
   design specifically fixes (see `project.md` and
   `tests/test_target_save.py::test_cross_enduser_saves_accumulate_without_clobbering`), and it
   would also mean an end user's autosave silently publishes to the database before they're
   ready to ship.
3. **End users only ever see rows where `RawRow.assigned_enduser_id` matches their session.**
   `GET /review/grid` and `POST /review/save` both enforce this — a row not assigned to the
   caller is invisible in the grid and rejected (422) if targeted by a save.
4. **A row has exactly one assigned end user — this is permanent, not a placeholder.** Rows can
   be shared two ways: a single-row `PUT /admin/datasets/{dataset_id}/rows/{row_index}/assign`,
   or a multi-select bulk share via `PUT /admin/datasets/{dataset_id}/rows/assign-bulk`
   (checkboxes + "Share selected rows with" in the admin UI). Both write the same
   `RawRow.assigned_enduser_id` single FK. Confirmed with the project owner: two end users must
   never see the same row — don't add a many-to-many (join table) here even as an option; the
   single-FK model is the intended design, not a POC shortcut.
5. **Datasets coexist — ingesting never wipes a prior dataset.** `create_new_dataset` always
   inserts a new `Dataset` row; every admin dataset-scoped route takes an explicit
   `dataset_id` path parameter (`/admin/datasets/{dataset_id}/...`) rather than resolving an
   implicit "active" one. When adding a new admin endpoint that touches dataset-scoped data,
   require and validate `dataset_id` the same way the existing ones do (`_get_dataset` in
   `app/routers/admin.py`) — don't reintroduce a singleton "current dataset" concept.
6. **Admin-added columns are always editable and always in the grid, independent of
   `ExposedColumn`.** A `ColumnDef` with `is_admin_added=True` doesn't go through the 4–6
   exposed-column selection or a per-cell `CellEditRule` — every row assigned to an end user
   gets an editable cell in that column automatically (`app/routers/review.py::get_grid`), and
   `apply_enduser_edits` validates its value against the column's own `input_type`/`options`
   instead of a `CellEditRule`. Don't collapse these into one mechanism — an ingested column's
   editability is per-cell and admin-flagged; an admin-added column's is per-column and
   inherent. Free-text admin columns are capped at `MAX_FREE_TEXT_LENGTH` (`app/target.py`).
7. **Autosave always goes through `POST /review/save` → `apply_enduser_edits`.** The end-user
   grid fires a save on every cell change (debounced for free-text inputs) rather than batching
   until a button click, but every autosave call — and the "Ship to DB" button — hit the same
   validated code paths as any other request. Don't add a "fast path" that writes a
   `CellEditValue` or touches the target table without going through `apply_enduser_edits` /
   `ship_dataset_to_db`.
8. **A row belongs to exactly one dataset; `row_index` is only unique within that dataset.**
   `POST /review/save` therefore takes an explicit `dataset_id` alongside its edits — never
   assume a `row_index` is globally unique or try to infer which dataset it belongs to.
9. **An end user's grid aggregates across every dataset they have assigned rows in**
   (`GET /review/grid` returns `{datasets: [...]}`, one entry per dataset with rows for that
   caller). Shipping is per-dataset (`POST /review/datasets/{dataset_id}/ship`) — an end user can
   ship a dataset only if they have at least one row assigned in it; admins can ship any dataset
   via `POST /admin/datasets/{dataset_id}/ship`. Don't add a "ship everything" action that
   iterates datasets implicitly — shipping is always scoped to one dataset at a time.
10. **`master_admin` and `admin` are both full admins; the only difference is who can manage
    admin accounts.** `require_admin`/`require_admin_page` accept either role — don't scope any
    existing admin feature to `master_admin` only. The `master_router` in
    `app/routers/admin.py` (gated by `require_master_admin`) is exclusively for
    `GET/POST/DELETE /admin/admins` — if you're tempted to restrict some other admin action to
    master-admin-only, that's a new product decision, not something to infer from this pattern.

## Model selection

| Model | Use when |
|-------|----------|
| `claude-sonnet-5` | Default — most tasks in this product: route/endpoint changes, template/JS edits, test writing. |
| `claude-opus-4-8` | Schema changes, anything touching `app/sanitize.py`/`app/target.py` identifier or save-merge logic, auth changes, or other security-sensitive edits. |
| `claude-haiku-4-5` | Small, mechanical, low-risk edits (copy tweaks, renames, doc updates). |

The table above is this product's Claude-tier defaults. For whether a given task should run on a
local/open model instead of Claude at all, follow the ecosystem's routing policy in
`default-multi-ai`'s `CLAUDE.md` rather than deciding ad hoc.

## Skills

| Trigger | File | Description |
|---------|------|-------------|
| "qa this", "test the POC" | `.claude/skills/qa/SKILL.md` | How to verify a change end-to-end: pytest, then the manual golden-path check (ingest → configure → per-end-user scoping → save → cross-user accumulation). |
| "frontend work", template/JS/CSS changes | `.claude/skills/frontend/SKILL.md` | Conventions for `app/templates/` + `app/static/` (no build step, `api()` fetch wrapper, table-rendering pattern), plus the pending `maya-math` design-reference direction. |
| "backend work", router/model/schema changes | `.claude/skills/backend/SKILL.md` | FastAPI router structure, SQLAlchemy model conventions, and the identifier-safety / save-merge invariants above. |

## Agents

| Name | Type | File | Scope |
|------|------|------|-------|
| qa | general-purpose | `.claude/agents/qa.md` | Runs the test suite and the manual golden-path checklist against a change; reports pass/fail with specifics, doesn't fix code itself. |
| project-manager | general-purpose | `.claude/agents/project-manager.md` | Keeps `project.md`'s roadmap/status current, turns ambiguous asks into scoped tasks, flags when a request needs a data-model decision (e.g. one-row-many-end-users) rather than a quick UI patch. |

## Context hygiene

- Don't re-read files already in context unless they changed.
- Prefer `Grep`/`Glob` over broad `Read` sweeps of `app/` — it's small but no need to reload it
  wholesale for a targeted change.
- Run `pytest` (fast, ~5s) after any change to `app/ingestion.py`, `app/target.py`, or
  `app/sanitize.py` before considering the change done.
