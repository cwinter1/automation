# Project: Data Ingestion + Correction Rules POC

## What this is

A proof-of-concept web app for a data-correction workflow, built to demonstrate the pattern
before it's hardened into a real product:

1. **Ingest** — an admin brings in source data, either by uploading an `.xlsx` file or by
   pulling a table from an external database (via a named connection or a raw connection
   string). Every ingest creates a new, independent dataset — nothing is replaced or wiped, so
   the admin can bring in dataset after dataset over time, each with its own rules and end
   users, without losing earlier ones.
2. **Configure rules** — per dataset, the admin reviews the raw data, decides which 4–6 columns
   end users are allowed to see, flags the specific cells that need a human correction (each
   with its own dropdown of valid replacement values), can add wholly new blank columns or rows
   for end users to fill in, and decides who is responsible for which rows.
3. **Correct** — end users log in and see every row assigned to them, across every dataset
   they've been given rows in. Anything not flagged/admin-added is locked/read-only; editable
   cells are dropdowns or free text, never arbitrary edits to a locked field. Changes autosave
   immediately so nothing is lost, but nothing reaches the database until the corresponding
   dataset is explicitly **shipped** — by the end user or by the admin.

## Roles

Three tiers:

- **Master admin** — the single shared `ADMIN_PASSWORD`, no account of its own. Has full admin
  access (everything below) *plus* the exclusive ability to create/remove named admin accounts.
- **Admin** — individual username + password, created by the master admin. Full admin access:
  ingests data (each ingest a new dataset), defines exposed columns/custom columns/rows per
  dataset, flags cells, creates end-user accounts, assigns/shares rows, names each dataset's
  target table, can ship any dataset. Cannot manage other admin accounts — that's the one thing
  reserved for the master admin.
- **End user** — individual username + password, created by an admin. Sees and corrects only
  the rows assigned to them, across whichever dataset(s) they have rows in; never sees another
  end user's rows (confirmed permanent — a row has exactly one assigned end user, not many). Can
  ship a dataset only if they have at least one row assigned in it.

## Current status

The POC is functionally complete and tested (73 pytest cases + manual browser verification of
the full golden path, including cross-end-user save/ship accumulation, multi-dataset isolation,
and three-tier role gating). See `README.md` for how to run it and the intentional POC
limitations (no CSRF token, full-rewrite-on-ship).

## Architecture summary

FastAPI + SQLAlchemy + SQLite, server-rendered Jinja2 templates, vanilla JS (no frontend build
step). See `CLAUDE.md` for the file-by-file breakdown and the invariants that must not regress.

Two design decisions worth restating here:

- **Datasets coexist.** Ingesting never wipes a prior dataset — each ingest creates a new one,
  independently configured, with its own end-user assignments and target table.
- **Autosave (persist) and Ship (publish) are separate.** End-user edits save immediately into
  the app's own storage (`CellEditValue`) as they work, but the target table is only rewritten
  when a dataset is explicitly shipped — computed from *every* persisted edit across *every* end
  user at that moment, not just whoever just clicked Ship. This is what lets two different end
  users ship their own work independently without one clobbering the other's earlier
  corrections.

## Features delivered

- xlsx upload ingestion and generic DB-connector ingestion (via a named `DB_CONN_<NAME>`
  connection or a raw connection string), both fully working, converging on the same internal
  row representation. Every ingest creates a new dataset alongside any existing ones.
- Named DB connections (`app/connections.py`): configured via `DB_CONN_<NAME>` env vars, listed
  by name only to the admin UI (`GET /admin/db-connections`) — the actual connection strings
  never leave the server.
- Admin panel: dataset picker (switch which dataset you're configuring), raw data view,
  exposed-column selection (4–6, checkboxes), per-cell flagging with custom dropdown options,
  end-user account management, per-dataset target-table naming, per-dataset metadata view
  (`GET /admin/datasets/{id}/metadata` — input/output column schema, read live), and a manual
  "Ship to DB now" action.
- Row assignment, two ways: a per-row "Assign to" dropdown, or a multi-select bulk share
  (`PUT /admin/datasets/{id}/rows/assign-bulk`). Both write to the same
  `RawRow.assigned_enduser_id` field — bulk assignment is a UX convenience, not a different data
  model.
- **Custom columns**: admin adds a blank column that doesn't exist in the source data
  (`POST /admin/datasets/{id}/columns`, name + type), typed as either a fixed dropdown
  (admin-defined options) or free text (up to 500 characters). Always shown to every end user
  with an assigned row, independent of the 4–6 exposed-column selection.
- **Custom rows**: admin adds a wholly blank row (`POST /admin/datasets/{id}/rows`, no source
  data) that's assignable and flaggable exactly like an ingested row.
- End-user grid: aggregates across every dataset the caller has rows in, one section per
  dataset, each scoped to that caller's assigned rows only. A search box filters the visible
  rows client-side; the same search box is on the admin's raw-data table.
- **Autosave**: every cell edit persists immediately (debounced for free-text fields) via
  `POST /review/save`, with an inline per-cell status ("Saving…" / "Saved" / error). This never
  touches the target table on its own.
- **Ship to DB**: an explicit action, available to both end users (per dataset they have rows
  in) and admins (any dataset), that publishes the dataset's current state — raw data plus every
  persisted edit from every end user — into the target table. Rejects (403) an end user shipping
  a dataset they have no rows in; rejects (400) shipping before a target table name is set.
- Ownership/option validation on every edit that rejects tampered requests with a 422, whether
  submitted via autosave or otherwise.
- **Admin directory**: a master admin (the original shared `ADMIN_PASSWORD`) can create/remove
  named admin accounts (`POST/GET/DELETE /admin/admins`, master-admin-only). A named admin has
  identical access to everything else an admin can do — the only restriction is that only the
  master admin can manage admin accounts themselves.

## Confirmed design decisions (not open questions)

- **A row has exactly one assigned end user, permanently.** Explicitly confirmed with the
  project owner — this is not a POC shortcut to revisit later. Two end users must never see the
  same row. Don't propose or build a many-to-many row/end-user model.

## Roadmap / not yet built

These are explicitly out of scope for the current POC but the schema/architecture was kept
flexible enough to add them without a rewrite:

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
