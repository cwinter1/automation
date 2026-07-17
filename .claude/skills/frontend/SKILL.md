---
name: frontend
description: Conventions for this POC's frontend (Jinja2 templates + vanilla JS/CSS, no build step) and the token-based design system in app.css — a brand-neutral placeholder pending maya-math repo access or the user's screenshots.
origin: project
---

# Frontend Patterns for the Data Ingestion POC

## When to Activate

- Editing anything in `app/templates/` or `app/static/`.
- Adding a new admin or end-user UI control.
- Any request about "how the app should look" or design direction.

## How It Works

### Current stack — deliberately minimal

There is **no build step, no framework, no bundler**. This is intentional for a POC — don't
introduce React/Vue/a bundler/npm without an explicit ask, even if it would make a given change
easier. The pattern is:

- `app/templates/base.html` — shared shell (topbar, session-aware logout, `<script src="/static/app.js" defer>`).
- `app/templates/admin.html`, `review.html`, `login.html` — extend `base.html`, define static
  HTML skeletons (forms, empty `<div>` mount points like `#raw-table-wrap`, `#grid-wrap`) that
  `app.js` fills in via `fetch` + DOM APIs.
- `app/static/app.js` — one file, two entry points (`initAdminPage()`, `initReviewPage()`),
  gated on `DOMContentLoaded` by checking which page-specific mount point exists in the DOM.
  A single `api(method, url, body)` helper wraps `fetch`, handles JSON vs. `FormData` bodies,
  and throws with a readable message on non-2xx — every new call should go through it rather
  than a fresh `fetch()`.
- `app/static/app.css` — a token-based design system: color/spacing/radius/shadow custom
  properties defined in `:root`, overridden under `@media (prefers-color-scheme: dark)`. See
  "Design system" below. Follow this pattern for any new color or spacing value — don't
  hardcode hex values or magic pixel numbers in rules; add or reuse a token instead.

### Adding a new admin control (pattern to follow)

The multi-select bulk row-share feature is the reference example for "add a new admin
interaction":

1. Schema (`app/schemas.py`): a request/response Pydantic model.
2. Endpoint (`app/routers/admin.py`): dataset-scoped controls take `dataset_id` as a path
   parameter and validate inputs against that specific dataset before writing.
3. Static skeleton (`admin.html`): a small, clearly-labeled control block (see
   `.bulk-assign-bar`), not woven into the existing table markup.
4. `app.js`: extend `state`, add a `render*()` function if there's new state to reflect, wire
   the control's event listener near the other form handlers at the bottom of `initAdminPage()`.
5. `app.css`: reuse existing custom properties; add a new class scoped to the new control.

### Client-side search filter

`attachSearchFilter(inputEl, wrapEl)` in `app.js` is a generic, reusable helper — it wires an
`<input type="search">` to hide/show `<tbody> <tr>` elements in a given table wrapper by
substring match against each row's text content. Both the admin raw table and the end-user grid
use it (`#raw-table-search`, `#grid-search`). It's pure client-side (no backend call), so it's
the right tool for "filter what's already loaded" — don't add a server-side search endpoint
unless a table grows large enough that loading everything client-side stops being reasonable.
Call the filter function again after any re-render (`applyRawTableFilter()` /
`applyGridFilter()`) so the current search term still applies to freshly-rendered rows.

### Autosave vs. Ship (end-user grid)

Editable cells in `review.html` save on `change` (dropdowns) or a `debounce`d `input` event
(free text, ~500ms) — see `saveOneEdit()` in `initReviewPage()`. Each editable `<td>` gets its
own `.cell-status` element showing "Saving…" / "Saved" / the error message, scoped to that cell
so one failing save doesn't clobber another cell's status. This only persists the edit
(`POST /review/save`) — it does **not** publish to the target table.

Each dataset section (`renderDatasetSection()`) has its own "Ship to DB" button
(`POST /review/datasets/{id}/ship`), since shipping is a per-dataset action and an end user may
have rows in several datasets at once (see `.claude/skills/backend/SKILL.md`'s multi-dataset
note). Don't add a page-level "ship everything" button — always scope shipping to one dataset
section.

### Multi-dataset grid layout

The grid API returns `{datasets: [...]}`, so `initReviewPage()` renders one
`.dataset-section` per entry (heading + its own table + its own Ship button + its own status
line) rather than one flat table. `attachSearchFilter` still works unmodified across multiple
sections since it filters any `<tbody> <tr>` under the wrapping `#grid-wrap`, regardless of how
many `<table>`s are inside it.

On the admin side, `admin.html`'s "1. Datasets" section holds a `<select id="dataset-select">`
populated from `GET /admin/datasets`; `state.currentDatasetId` in `app.js` drives every
subsequent dataset-scoped call. Ingesting sets `state.currentDatasetId` to the newly-created
dataset and refreshes — a new ingest doesn't require the admin to manually find and select it.

### Admin-added ("custom") columns are visually distinct, not click-to-configure

Ingested columns use the existing "click a cell to flag/configure" pattern (`onCellClick`). A
custom column (`ColumnDef.is_admin_added`) is configured once at creation time (the "4. Custom
columns" form) — its cells in the admin raw table are marked with `.admin-col-cell` /
`.admin-col-header` (a distinct background color) but have no click handler, since there's
nothing per-cell to configure. Don't add a click-to-flag interaction to custom-column cells; if
the admin needs to change a custom column's type/options, that's a delete-and-recreate today
(see the `.claude/skills/backend/SKILL.md` note on the two kinds of editability).

### Design system (placeholder, pending maya-math/screenshots)

`app/static/app.css` opens with a documented token block: color (`--color-bg`,
`--color-surface`, `--color-border(-strong)`, `--color-text(-muted)`, `--color-primary(-hover)`,
`--color-danger(-bg)`, `--color-success`, `--color-warning-bg/border`, `--color-accent-bg/border`),
spacing (`--space-1` … `--space-6`), radius (`--radius-sm/md/lg`), shadow (`--shadow-sm/md`), and
`--font-sans`. Every component rule below it (panels, buttons, inputs, tables, the login cards,
`.dataset-section`, flagged/admin-column highlighting) is built from these tokens, not hardcoded
values — that's deliberate: swapping in the real design later should mean editing the `:root` /
dark-mode token values, not rewriting component rules.

This is explicitly a **brand-neutral placeholder**, not the final design. Per the project owner:

- **Default reference: the `maya-math` repo's conventions** (colors, layout, component
  patterns) — pull this in once that repo is accessible in-session (`add_repo`/`list_repos` have
  hit a persistent infra approval gate all session as of this writing; it did not clear on
  repeated retries across several hours, so don't assume one more retry will do it — but don't
  assume it's permanent either, it may just need a fresh session or explicit connector
  approval).
- **Overriding source of truth: user-provided screenshots**, to be uploaded later. When either
  lands, update the token values (and only the token values, where possible) to match, and note
  here what changed so future sessions don't revert to this placeholder's interpretation.

Don't restyle component-by-component when that day comes — retheme via the tokens first, and
only touch individual component rules if the real design genuinely needs a different shape
(e.g. a different button style), not just different colors.

## Examples

- Adding a delete-confirmation dialog for end users: reuse `window.confirm()` (see the pattern
  in `onCellClick`'s `window.prompt()` usage) rather than building a custom modal component —
  matches the project's "plain until told otherwise" design posture.
- Restyling once `maya-math`/screenshots are available: start by changing the token values in
  `:root` and the dark-mode block; the `app.js` logic (form submit handlers, rendering) shouldn't
  need to change for a visual-only update.
