---
title: Data Ingestion + Correction Rules POC — Playbook
---

# Data Ingestion + Correction Rules POC

A copy-adaptable set of prompts for rebuilding (or continuing) the data-ingestion +
correction-rules POC in a different environment — e.g. a company Claude Code workspace that
doesn't have this session's history.

This copy lives inside the reference implementation itself (this repo, `cwinter1/automation`)
so the repo you'd fork into production is self-contained — the build reasoning travels with the
code, not just the code. The canonical, cross-project version of this playbook (kept in sync
with this one) lives in [`cwinter1/ai-playbooks`](https://github.com/cwinter1/ai-playbooks)'s
`playbooks/data-ingestion-correction-poc/`, alongside other, unrelated playbooks — use that repo
if you're starting a *different* kind of project and just want the general pattern.

**What it builds**: admins ingest data (xlsx or a DB pull), define which rows/cells end users
may see and correct through a constrained UI (dropdowns, not free text), end users log in and
correct only their assigned rows, and corrections publish to a target database table on demand.
See `../../CLAUDE.md` in this repo for the full architecture this playbook produces — it's the
reference implementation these prompts were extracted from.

## How to use this

Each numbered file is a single prompt, meant to be pasted into a fresh Claude Code session **in
order** — later prompts assume the product decisions and files from earlier ones already exist.
Every file has three parts:

1. **Context** — why this step exists and what it assumes is already true.
2. **Prompt** — paste this verbatim (or lightly adapt the nouns — company name, table names,
   role names) into Claude Code.
3. **Expect / confirm** — the clarifying questions Claude is likely to ask and the answers that
   keep this build consistent with the reference implementation, plus a short checklist of what
   should exist once the step is done.

`invariants.md` is not a prompt — it's a standing reference of the product decisions that were
explicitly confirmed and must **not** be re-litigated or "improved" by a later session. Paste it
into your project's `CLAUDE.md` after step 1 so every subsequent session inherits it.

## Sequence

| # | File | Delivers |
|---|------|----------|
| 1 | `01-seed-prompt-initial-poc.md` | Core POC: ingestion (xlsx + DB), admin rule-setting, per-cell dropdown corrections, per-end-user row scoping, save-to-target-table |
| 2 | `02-bulk-row-share.md` | Admin multi-select bulk row assignment |
| 3 | `03-custom-columns-autosave-search.md` | Admin-added blank columns, grid autosave, search boxes |
| 4 | `04-multi-dataset-ship-split-connections-admin-rows.md` | Multiple coexisting datasets, save-vs-ship split, named DB connections, admin-added rows, metadata endpoint |
| 5 | `05-admin-directory-three-tier.md` | Master admin / named admin / end user three-tier directory |
| 6 | `06-design-system-placeholder.md` | Token-based CSS design system, placeholder pending your real brand |
| 7 | `07-verification-agents.md` | Independent QA / product / frontend / backend-architecture verification pass |
| — | `invariants.md` | Confirmed product decisions — paste into `CLAUDE.md`, don't re-ask these |
| — | `enterprise-readiness-template.md` | Template for the "what's missing to go live" doc — fill in against your actual target infra |

## Model selection while running this

Follow this repo's own guidance (`../../CLAUDE.md`): default to your standard model for most of
these prompts; step 1 (initial architecture) and step 4 (schema/save-merge logic) are the two
most worth a stronger reasoning model if your workspace has one, since they set data-model
decisions that are expensive to change later.

## Adapting for your company environment

- **Stack**: prompts assume Python/FastAPI/SQLAlchemy/SQLite + server-rendered Jinja2/vanilla
  JS, no build step. If your company has a mandated stack, say so explicitly in step 1's prompt
  — everything downstream is stack-agnostic in intent even though the reference implementation
  isn't.
- **Auth**: step 5's three-tier model (master admin / admin / end user) assumes you want that
  exact hierarchy. If your company already has SSO/an identity provider, replace step 5 with a
  prompt describing your actual auth requirement instead — don't bolt this scheme on top of SSO.
- **Target database**: the "ship to DB" step assumes a SQL target table with admin-controlled
  naming. If your company's downstream system isn't a SQL table (an API, a message queue, a
  data lake), say so in step 4's prompt instead of forcing the DB-table shape.
- **Design**: step 6 produces a brand-neutral placeholder on purpose. Point Claude at your real
  design system or screenshots at that step rather than letting it invent a palette — see that
  file's notes.
