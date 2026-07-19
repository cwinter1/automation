---
name: backend
description: FastAPI/SQLAlchemy conventions for this POC — router structure, model patterns, and the identifier-safety / save-merge invariants that must not regress.
origin: project
---

# Backend Patterns for the Data Ingestion POC

## When to Activate

- Adding or changing an endpoint in `app/routers/`.
- Adding or changing a model in `app/models.py`.
- Touching `app/ingestion.py`, `app/target.py`, `app/sanitize.py`, or `app/auth.py`.

## How It Works

### Router structure

Each router module splits into two `APIRouter`s with role-gating applied at the router level
(not per-route, so it can't be forgotten on a new endpoint):

```python
pages_router = APIRouter(dependencies=[Depends(require_admin_page)])   # HTML pages, redirects to /login on auth failure
api_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])  # JSON API, 403 on auth failure
```

New admin-only endpoints go on `api_router`; new admin-only pages go on `pages_router`. Same
pattern in `app/routers/review.py` for the end-user role. Don't add an endpoint outside these
two routers per file — it would skip the role check.

### Three roles, two admin-gating dependencies

`master_admin` (the shared `ADMIN_PASSWORD`) and `admin` (a named `AdminUser` account) are both
full admins — `require_admin`/`require_admin_page` accept either. `app/routers/admin.py` also
has a third router, `master_router` (same `/admin` prefix, gated by `require_master_admin`),
used *only* for `GET/POST/DELETE /admin/admins` — admin-account management is the one thing
reserved for the master admin. Don't move an existing admin feature onto `master_router` without
that being an explicit product decision; the default for any new admin endpoint is `api_router`
(both roles), not `master_router`.

### Model conventions (`app/models.py`)

- Every domain table hangs off `dataset_id` with `ForeignKey(..., ondelete="CASCADE")`. Datasets
  coexist (`create_new_dataset` never deletes a prior one) — the cascade exists for deleting a
  single dataset explicitly if that's ever added, not for a wipe-on-ingest flow. SQLite doesn't
  enforce FKs by default — `app/db.py` turns it on via a `PRAGMA foreign_keys=ON` connect
  listener; don't remove that.
- Every dataset-scoped admin route takes `dataset_id` as an explicit path parameter
  (`/admin/datasets/{dataset_id}/...`) and resolves it via `_get_dataset(db, dataset_id)` (404 if
  not found). There is no implicit "current" or "active" dataset anywhere in the backend — that
  concept only exists client-side, as which dataset the admin UI currently has selected.
- Cell-level rules/values reference columns by `column_def_id` (FK to `ColumnDef.id`), never by
  raw string name — avoids drift if a column is renamed.
- `RawRow.data` is a JSON blob keyed by `ColumnDef.safe_name`, not the original source header —
  source data can have arbitrary/duplicate/blank headers; `safe_name` is what's guaranteed valid
  as both a JSON key and (later) a SQL identifier.

### The identifier-safety invariant

`app/sanitize.py::validate_identifier` is the only function allowed to approve a string for use
as a SQL identifier (table or column name) in dynamically built DDL/DML. Every call site that
builds `CREATE TABLE`/`INSERT` SQL (`app/target.py`) validates first and never mutates on
failure — the caller gets a clear error instead of a silently-rewritten identifier. Values
always go through SQLAlchemy bound parameters; only identifiers go through this manual path,
because parameterization doesn't cover identifier position. Any new dynamic-SQL code must follow
this same shape — validate-or-raise, then interpolate.

### Save vs. ship — two independent functions in `app/target.py`

- `apply_enduser_edits(db, dataset, enduser_id, edits)` — validates ownership/editability/value,
  then upserts `CellEditValue` rows. Nothing else. This is what `POST /review/save` (autosave)
  calls, every time, on every cell change.
- `ship_dataset_to_db(db, dataset)` — takes no edits; rebuilds the corrected row set from *all*
  persisted `CellEditValue` rows (`build_corrected_rows`) and rewrites the target table
  (`create_or_replace_target_table` + `insert_corrected_rows`, inside one `engine.begin()`
  transaction so a failure never leaves a half-written table). This is what
  `POST /review/datasets/{id}/ship` and `POST /admin/datasets/{id}/ship` call.

These must stay separate functions with separate call sites (see `CLAUDE.md` Invariant #2) — if
you're adding a new kind of edit, route it through `apply_enduser_edits`; if you're adding a new
publish trigger, route it through `ship_dataset_to_db`. Never have an edit-persisting endpoint
also rebuild the target table.

### Bulk operations

`PUT /admin/datasets/{dataset_id}/rows/assign-bulk` is the reference pattern for a bulk admin
action: validate all inputs up front (every `row_index` exists, `enduser_id` exists if given)
before writing anything, then do the actual mutation as a single
`UPDATE ... WHERE row_index IN (...)` rather than a loop of individual writes.

### Two kinds of cell editability — don't conflate them

An ingested column's cells are editable **per-cell**: a `CellEditRule` on a specific
`(row_index, column_def_id)` flags just that one cell, with its own options. An admin-added
column (`ColumnDef.is_admin_added=True`) is editable **per-column**: every row assigned to an
end user gets an editable cell in that column automatically, typed by the column's own
`input_type`/`options` — there's no per-cell rule to create. `apply_enduser_edits`
(`app/target.py`) checks admin-added columns first (dropdown → value must be in `options`; text
→ length-capped, any value) and falls back to the `CellEditRule` path otherwise. `get_grid`
(`app/routers/review.py`) does the same two-branch check when deciding `editable`/`input_type`
for each cell. If you add a third kind of editability, keep it as an explicit third branch in
both places — don't try to unify it into `CellEditRule` just because that's how ingested columns
work.

### Autosave doesn't get a different validation path

The end-user grid saves on every change (see `.claude/skills/frontend/SKILL.md`), but that's
purely a frontend timing decision — every autosave call hits the identical
`POST /review/save` → `apply_enduser_edits` pipeline. Never add an endpoint or code path that
writes a `CellEditValue` without going through `apply_enduser_edits`'s ownership/validity checks,
even for a "just save this one field, it's obviously fine" case. `apply_enduser_edits` never
touches the target table — see the save-vs-ship split above.

### Multi-dataset: a row's identity always includes its dataset

`row_index` is only unique *within* a dataset (see `CLAUDE.md` Invariant #8). Any new endpoint
or function that takes a `row_index` must also take (or already be scoped to) a `dataset_id` —
never assume a bare `row_index` is enough to find the right row. `GET /review/grid` returns
`{datasets: [...]}`, one section per dataset the caller has rows in
(`app/routers/review.py::_build_dataset_grid`) — if you're adding a new cross-cutting end-user
view, follow that shape rather than flattening rows from different datasets into one list.

## Examples

- Adding a new admin-configurable rule type: model it like `CellEditRule` (dataset-scoped,
  references `column_def_id`, has a `UniqueConstraint` on the natural key) rather than
  free-floating.
- Adding a new dynamic-SQL feature (e.g. exporting to a second table): reuse
  `validate_identifier`, don't write a new regex.
