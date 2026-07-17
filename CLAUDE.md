# CLAUDE.md

Guidance for Claude Code sessions working in this repository. For the product spec, roles, and
roadmap, see `project.md`. For run instructions and known POC limitations, see `README.md`.

## Project overview

A FastAPI proof-of-concept: admins ingest data (xlsx upload or a generic DB-connector pull),
define which columns/cells end users may see and correct, and end users make constrained
corrections (dropdowns, not free text) that get saved into a new database table.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export ADMIN_PASSWORD=changeme SESSION_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
uvicorn app.main:app --reload   # http://localhost:8000/login

pytest   # full test suite
```

## Architecture

- `app/models.py` — SQLAlchemy models: `Dataset`, `ColumnDef`, `RawRow`, `ExposedColumn`,
  `CellEditRule`, `CellEditValue`, `TargetTableSetting`, `EndUser`. `ColumnDef` doubles as both
  an ingested source column and an admin-created blank column (`is_admin_added`, `input_type`,
  `options`) — see Invariant #6.
- `app/ingestion.py` — xlsx parsing and DB-connector pulling, both converging on
  `(columns, rows)`; `make_safe_identifier` for deriving safe SQL column names;
  `replace_active_dataset` for the single-active-dataset replace semantics.
- `app/sanitize.py` — `validate_identifier`, the one function every dynamically-built SQL
  identifier must pass through. See Invariants below.
- `app/auth.py` — shared admin password + per-end-user username/password, session-cookie based.
- `app/target.py` — the save pipeline: validate edits → persist to `CellEditValue` → merge with
  raw data → rewrite the target table in one transaction.
- `app/routers/admin.py`, `app/routers/review.py`, `app/routers/auth_router.py` — the three
  route groups (admin API/page, end-user API/page, login/logout).
- `app/templates/`, `app/static/` — Jinja2 templates + vanilla JS/CSS, no build step.
- `tests/` — pytest; `conftest.py` sets up an isolated temp SQLite DB per test.

## Invariants — do not regress these

1. **SQL identifiers are never string-interpolated without `validate_identifier()` first.** The
   target table name and every column safe-name are used in dynamically generated DDL/DML.
   Values always go through SQLAlchemy bound parameters; identifiers never do (they can't be
   parameterized), so they're checked against `IDENTIFIER_RE` instead. Any new code path that
   builds a table/column name from admin input must call `validate_identifier` first.
2. **Saves are computed from persisted `CellEditValue` rows, not just the current request's
   edits.** This is what lets two different end users save independently without one wiping out
   the other's earlier corrections. Do not "simplify" `save_corrected_dataset` back to only
   using the request payload — that reintroduces the clobbering bug this design specifically
   fixes (see `project.md` and `tests/test_target_save.py::test_cross_enduser_saves_accumulate_without_clobbering`).
3. **End users only ever see rows where `RawRow.assigned_enduser_id` matches their session.**
   `GET /review/grid` and `POST /review/save` both enforce this — a row not assigned to the
   caller is invisible in the grid and rejected (422) if targeted by a save.
4. **Rows can be shared with an end user two ways**: a single-row `PUT
   /admin/rows/{row_index}/assign`, or a multi-select bulk share via `PUT
   /admin/rows/assign-bulk` (checkboxes + "Share selected rows with" in the admin UI). Both
   write the same `RawRow.assigned_enduser_id` field — there is one owner per row today, not a
   many-to-many. If a future requirement needs a row visible to multiple end users at once, that
   is a data-model change (a join table), not just a UI change — flag it explicitly rather than
   bolting it onto the single FK.
5. **Single active dataset.** Re-ingesting wipes and replaces everything scoped to the previous
   `Dataset` (cascade). Don't assume multiple datasets coexist — see `project.md` roadmap for
   where that's headed.
6. **Admin-added columns are always editable and always in the grid, independent of
   `ExposedColumn`.** A `ColumnDef` with `is_admin_added=True` doesn't go through the 4–6
   exposed-column selection or a per-cell `CellEditRule` — every row assigned to an end user
   gets an editable cell in that column automatically (`app/routers/review.py::get_grid`), and
   `apply_enduser_edits` validates its value against the column's own `input_type`/`options`
   instead of a `CellEditRule`. Don't collapse these into one mechanism — an ingested column's
   editability is per-cell and admin-flagged; an admin-added column's is per-column and
   inherent. Free-text admin columns are capped at `MAX_FREE_TEXT_LENGTH` (`app/target.py`).
7. **Autosave and manual Save go through the exact same `POST /review/save` endpoint and the
   exact same validation.** The end-user grid fires a save on every cell change (debounced for
   free-text inputs) rather than batching until a button click — this is a frontend-only
   behavior change (`app/static/app.js`), not a relaxed backend contract. Don't add a separate
   "fast path" for autosave that skips `apply_enduser_edits`.

## Model selection

| Model | Use when |
|-------|----------|
| `claude-sonnet-5` | Default — most tasks in this repo: route/endpoint changes, template/JS edits, test writing. |
| `claude-opus-4-8` | Schema changes, anything touching `app/sanitize.py`/`app/target.py` identifier or save-merge logic, auth changes, or other security-sensitive edits. |
| `claude-haiku-4-5` | Small, mechanical, low-risk edits (copy tweaks, renames, doc updates). |

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
