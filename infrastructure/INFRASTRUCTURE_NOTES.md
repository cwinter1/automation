# infrastructure/

A self-contained, copy-paste bundle of this entire project — app code, tests, docs, and the
build playbook — meant to be lifted wholesale into a new environment (e.g. a company repo) to
bootstrap from the exact same state as this reference implementation.

This is a **copy**, not the working project. The live originals stay where the rest of the
tooling in this repo expects them:

| Here | Original |
|------|----------|
| `infrastructure/CLAUDE.md` | `/CLAUDE.md` (repo root — Claude Code auto-loads project instructions from this exact path, so the root copy can't move) |
| `infrastructure/README.md` | `/README.md` |
| `infrastructure/project.md` | `/project.md` |
| `infrastructure/ENTERPRISE_READINESS.md` | `/ENTERPRISE_READINESS.md` |
| `infrastructure/LICENSE` | `/LICENSE` |
| `infrastructure/.gitignore` | `/.gitignore` |
| `infrastructure/pytest.ini` | `/pytest.ini` (inert here — only the root copy is actually read; see below) |
| `infrastructure/.claude/` | `/.claude/` (skills + agents) |
| `infrastructure/docs/playbook/` | `/docs/playbook/` |
| `infrastructure/design/screenshots/` | `/design/screenshots/` |
| `infrastructure/app/`, `infrastructure/tests/`, `infrastructure/requirements.txt` | `/app/`, `/tests/`, `/requirements.txt` |

Every file at the repo root is mirrored here — this folder is a complete copy, not a curated
subset.

If you're extending *this* repo, edit the originals, not these copies — this folder isn't wired
into the running app. Note that Claude Code does auto-discover `.claude/skills/` wherever it
finds them, including here, so you'll see both an unscoped `backend`/`frontend`/`qa` skill (from
the root `.claude/`) and an `automation/infrastructure:`-prefixed duplicate of each; they're
identical content, just keep edits to the root originals so the two don't drift. Re-sync this
folder by hand (or regenerate it) if the originals change meaningfully and you want the copy to
stay current.

If you're bootstrapping a **new** environment: copy this folder's contents into the root of the
new repo (so `CLAUDE.md`, `.claude/`, `app/`, etc. land back at their expected paths there) and
follow `docs/playbook/README.md` from there.
