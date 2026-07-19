# CLAUDE.md

Guidance for Claude Code sessions working in this repository.

## What this repo is

`automation` is the **builder master repo**: the place where the patterns and playbooks defined
in [`ai-playbooks`](https://github.com/cwinter1/ai-playbooks) actually get built into running
products. This repo hosts one or more products, each self-contained under `products/<name>/`.
It is not itself a product — don't add application code at the repo root.

## Products

| Product | Folder | Docs |
|---------|--------|------|
| Data ingestion + correction rules POC | `products/data-ingestion-correction-poc/` | that folder's own `CLAUDE.md` |

Each product's `CLAUDE.md` is the authority on that product's architecture, invariants, and model
selection — don't duplicate product-specific detail here. This file only covers repo-wide
conventions that apply across every product.

## Starting a new product

Run `ai-playbooks/playbooks/new-builder-repo/README.md`'s prompt first, from this repo's root,
before writing any application code for a new product. It scaffolds the `products/<name>/`
folder (`README.md`, `CLAUDE.md`) and updates this file's and the root `README.md`'s products
tables.

## Skills and agents

Each product owns its own `.claude/skills` and `.claude/agents` inside `products/<name>/` —
see `products/data-ingestion-correction-poc/.claude/` for the reference layout. There is
currently no repo-root `.claude/`; add one only if a genuinely cross-product skill or agent
shows up (not speculatively).

## Model selection

For which Claude tier to use on a given task, follow the product's own `CLAUDE.md` (each
product's table may differ based on its risk profile). For whether a task should route to a
local/open model instead of Claude at all, follow the ecosystem-wide policy in
[`default-multi-ai`](https://github.com/cwinter1/default-multi-ai)'s `CLAUDE.md` — that repo is
the single source of truth for the local-vs-Claude decision; don't re-derive it here or in a
product's own docs.

## Ecosystem

This repo is one of three with a distinct role — see
[`ai-playbooks`'s `ECOSYSTEM.md`](https://github.com/cwinter1/ai-playbooks/blob/main/ECOSYSTEM.md).
