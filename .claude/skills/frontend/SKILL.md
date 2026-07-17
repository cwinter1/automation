---
name: frontend
description: Conventions for this POC's frontend (Jinja2 templates + vanilla JS/CSS, no build step) and the pending design direction — default to the maya-math repo's conventions until the user's screenshots land.
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
- `app/static/app.css` — CSS custom properties (`--border`, `--flag`, `--flag-border`) defined
  in `:root` and overridden under `@media (prefers-color-scheme: dark)`. Follow this pattern for
  any new color — don't hardcode hex values in rules.

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

### Design direction (pending)

The current UI has no real design system — it's functional, not styled to a brand. The intended
direction, per the project owner:

- **Default reference: the `maya-math` repo's conventions** (colors, layout, component
  patterns) — pull this in once that repo is accessible in-session (`add_repo` was gated behind
  an infra approval step as of this writing; retry it, don't assume it's permanently
  unavailable).
- **Overriding source of truth: user-provided screenshots**, to be uploaded later. When those
  arrive, they take priority over any inference from `maya-math` — update this section (and the
  actual CSS) to match them, and note here what changed and why so future sessions don't revert
  to the `maya-math`-only interpretation.

Until either lands, don't invest in a full visual redesign — keep changes functional and
minimal, consistent with the "no build step" constraint above, so the eventual redesign isn't
fighting scaffolding that will be thrown away.

## Examples

- Adding a delete-confirmation dialog for end users: reuse `window.confirm()` (see the pattern
  in `onCellClick`'s `window.prompt()` usage) rather than building a custom modal component —
  matches the project's "plain until told otherwise" design posture.
- Restyling the login page once `maya-math`/screenshots are available: touch only `app.css`
  custom properties and `login.html` markup; the `app.js` login-page logic (form submit
  handlers) shouldn't need to change for a visual-only update.
