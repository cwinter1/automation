# automation

The builder repo: where the playbooks and conventions from
[`ai-playbooks`](https://github.com/cwinter1/ai-playbooks) actually get built out. Each product
lives in its own `products/<name>/` subfolder with its own `README.md`, `CLAUDE.md`, tests, and
(if it needs them) its own `.claude/skills` and `.claude/agents` — products don't share code or
a stack unless a specific product decides to.

## Products

| Product | Delivers | Docs |
|---------|----------|------|
| [`data-ingestion-correction-poc`](./products/data-ingestion-correction-poc/) | Admin-configured, per-cell-correction workflow: xlsx/DB ingestion, per-cell dropdown corrections, per-end-user row scoping, autosave-vs-publish split, multi-dataset support, three-tier admin directory | [README](./products/data-ingestion-correction-poc/README.md) · [CLAUDE.md](./products/data-ingestion-correction-poc/CLAUDE.md) |

## Starting a new product

Follow `ai-playbooks/playbooks/new-builder-repo/README.md` to scaffold a new `products/<name>/`
folder before writing any application code.

## Ecosystem

This repo is one of three with a distinct role — see
[`ai-playbooks`'s `ECOSYSTEM.md`](https://github.com/cwinter1/ai-playbooks/blob/main/ECOSYSTEM.md)
for how it relates to `ai-playbooks` (doctrine) and
[`default-multi-ai`](https://github.com/cwinter1/default-multi-ai) (the ecosystem's
local-vs-Claude model routing policy).
