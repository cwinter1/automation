# Project: Data Ingestion + Correction Rules POC

## What this is

A proof-of-concept web app for a data-correction workflow, built to demonstrate the pattern
before it's hardened into a real product:

1. **Ingest** — an admin brings in source data, either by uploading an `.xlsx` file or by
   pointing at a table in an external database via a connection string.
2. **Configure rules** — the admin reviews the raw data, decides which 4–6 columns end users
   are allowed to see, flags the specific cells that need a human correction (each with its own
   dropdown of valid replacement values), and decides who is responsible for which rows.
3. **Correct** — end users log in and see only the rows given to them. Anything not flagged is
   locked/read-only; flagged cells are dropdowns, not free text, so corrections can't introduce
   new mistakes. Saving writes a full corrected copy of the dataset into an admin-named target
   table.

## Roles

- **Admin** — one shared password (`ADMIN_PASSWORD`). Ingests data, defines exposed columns,
  flags cells, creates end-user accounts, assigns/shares rows, names the target table.
- **End user** — individual username + password, created by the admin. Sees and corrects only
  the rows assigned to them; never sees another end user's rows.

## Current status

The POC is functionally complete and tested (pytest suite + manual browser verification of the
full golden path, including the cross-end-user save-accumulation guarantee). See `README.md`
for how to run it and the intentional POC limitations (single active dataset, no admin
directory, no CSRF token, full-rewrite-on-save).

## Architecture summary

FastAPI + SQLAlchemy + SQLite, server-rendered Jinja2 templates, vanilla JS (no frontend build
step). See `CLAUDE.md` for the file-by-file breakdown and the invariants that must not regress.

Key design decision worth restating here: saves are computed from **persisted** per-cell edits
(`CellEditValue`), not just the edits in the current request, and the target table is fully
rewritten from all persisted edits on every save. This is what lets two different end users save
their own rows independently without one clobbering the other's earlier corrections.

## Features delivered

- xlsx upload ingestion and generic DB-connector ingestion, both fully working, converging on
  the same internal row representation.
- Admin panel: raw data view, exposed-column selection (4–6, checkboxes), per-cell flagging with
  custom dropdown options, end-user account management, target-table naming.
- Row assignment, two ways:
  - Per-row "Assign to" dropdown for a single row.
  - **Multi-select bulk share**: tick multiple rows via checkboxes, pick an end user from
    "Share selected rows with", and assign them all in one action
    (`PUT /admin/rows/assign-bulk`). Both paths write to the same `RawRow.assigned_enduser_id`
    field — bulk assignment is a UX convenience, not a different data model.
- **Custom columns**: admin adds a blank column that doesn't exist in the source data (`POST
  /admin/columns`, name + type), typed as either a fixed dropdown (admin-defined options) or
  free text (up to 500 characters). Custom columns are always shown to every end user with an
  assigned row — they don't go through the 4–6 exposed-column selection or per-cell flagging,
  since the whole column is inherently editable by design. Deletable via `DELETE
  /admin/columns/{id}` (ingested columns cannot be deleted this way).
- End-user grid: strictly scoped to the caller's assigned rows, read-only vs. editable cells
  (dropdown or free text) driven entirely by server-side rule state. A search box filters the
  visible rows client-side; the same search box is on the admin's raw-data table.
- **Autosave**: every cell edit saves immediately (debounced for free-text fields) through the
  same validated `POST /review/save` endpoint used by the manual Save button — no separate
  "fast path," no relaxed validation. An inline per-cell status ("Saving…" / "Saved" / error)
  gives feedback without needing to click Save.
- Save flow with cross-end-user accumulation (see above) and ownership/option validation that
  rejects tampered requests with a 422.

## Roadmap / not yet built

These are explicitly out of scope for the current POC but the schema/architecture was kept
flexible enough to add them without a rewrite:

- **Multiple concurrent datasets.** Today ingesting new data replaces the single active dataset
  entirely. The stated future direction: several named datasets exist at once, and the admin
  decides which dataset goes to which end user (a `DatasetAccess`-style join table is the
  natural extension — see `CLAUDE.md` invariants).
- **A real admin directory.** Today there's one shared `ADMIN_PASSWORD` for all admin access.
  Multiple named admin accounts (mirroring how end users already work) are planned.
- **Frontend redesign.** The current UI is intentionally plain (no design system, no build
  step) — it exists to prove the workflow, not to be the final look. The design direction for
  the real frontend is meant to follow the **`maya-math`** repo's conventions as the default
  reference. The user will also upload concrete screenshots of the target look later — once
  those land, treat them as the source of truth over any inference from `maya-math`, and update
  `.claude/skills/frontend/SKILL.md` accordingly.

## Where things live

- `README.md` — run instructions, POC limitations.
- `CLAUDE.md` — guidance for Claude Code sessions working in this repo (architecture, key
  invariants, model selection, skills/agents registry).
- `app/` — the application itself (see `CLAUDE.md` for the file map).
- `tests/` — pytest suite.
- `.claude/skills/`, `.claude/agents/` — project-specific Claude Code skills and agents (QA, frontend, backend,
  project-manager) for working on this codebase.
