# Enterprise Readiness — POC to Live

This POC is functionally complete for its intended scope (see `project.md` for what's
delivered and `README.md` for how to run it). This document lists what's missing to run it as
a real, multi-user, production system, and what's recommended once it gets there.

Nothing here blocks continued POC use or demoing. Treat it as the backlog for "next phase,"
grouped by how urgent it is once real users and real data are involved.

---

## 1. Data layer — the biggest gap

- **Move off SQLite to Postgres/MySQL.** SQLite's single-writer lock is the real ceiling for
  concurrent admins and end users. `DATABASE_URL` (`app/config.py`) is already env-driven, so
  this is a connection-string + driver change, not a rewrite — but every SQLite-specific
  assumption (the `PRAGMA foreign_keys=ON` listener in `app/db.py`, `DROP TABLE IF EXISTS` +
  `CREATE TABLE` in `ship_dataset_to_db`) should be re-verified against the target engine.
- **Add real migrations (Alembic).** `app/main.py` currently calls
  `Base.metadata.create_all(bind=engine)` on startup — there's no way to evolve the schema in
  place without wiping/recreating tables. This is the first thing that will hurt once there's
  real data in a shared database.
- **Add the missing index**: a composite index on `RawRow(dataset_id, assigned_enduser_id)` —
  every end-user grid load and admin row-assignment view filters on this pair.
- **Paginate.** The admin raw-data table and `GET /admin/datasets/{id}/metadata` load the full
  table into memory and render it whole; fine for a POC-sized dataset, not for tens of
  thousands of rows.
- **Decide on ship history.** `ship_dataset_to_db` (`app/target.py`) does a full
  `DROP TABLE` + rebuild on every ship — there's no record of what changed between ships or who
  shipped what. Live use likely wants either an append/versioned target table or a separate
  ship-audit log.
- **Dataset retention/archival.** Nothing currently deletes or archives old datasets — they
  accumulate indefinitely by design (Invariant #5 in `CLAUDE.md`). Fine for a POC; needs a
  retention policy before this runs unattended for years.

## 2. Security — must-do before real users touch it

- **CSRF protection.** Currently relies solely on `SameSite=Lax` cookies — called out as an
  intentional POC gap in `README.md`. Needs a real CSRF token before this is exposed beyond a
  trusted internal network.
- **Retire the shared `ADMIN_PASSWORD` master-admin model.** One shared password/env var with
  no rotation, no per-person accountability, and no way to revoke a single compromised
  credential without breaking everyone. Move the master admin to a real account.
- **Rate limiting / lockout on `/login`.** No attempt limiting exists today — `verify_admin_password`,
  `verify_admin_user_credentials`, and `verify_enduser_credentials` (`app/auth.py`) are called
  with no throttling in front of them.
- **Enforce TLS + secure cookies.** Nothing in `app/main.py` sets `Secure` on the session
  cookie or assumes HTTPS is terminated in front of it — needs a real reverse-proxy/TLS setup
  and cookie flags updated to match.
- **Audit logging.** Beyond `CellEditValue.edited_by_enduser_id`, nothing logs who created/removed
  users, who changed rules, or who shipped a dataset. Enterprise use needs a real audit trail,
  not just "last editor" on a cell.
- **Secrets management.** DB connection strings (`DB_CONN_<NAME>`), `ADMIN_PASSWORD`, and
  `SESSION_SECRET_KEY` are all plain environment variables today — fine for a POC, but should
  move to a real secrets manager (Vault, cloud KMS, etc.) before production credentials live in
  them.

## 3. Operability

- **No Dockerfile / CI pipeline yet.** Needed for repeatable, automated deploys instead of a
  manual `uvicorn app.main:app`.
- **No structured logging or error monitoring** (e.g. Sentry, structured JSON logs). Right now
  failures only surface as HTTP responses — there's no way to see what broke in production
  after the fact.
- **No backup strategy** for the database (SQLite file today, its Postgres/MySQL replacement
  tomorrow).
- **Health-check endpoint** for whatever orchestrator ends up running this (k8s liveness/readiness,
  a load balancer, etc.) — doesn't exist yet.

## 4. Product-level decisions still open

- **Real design/branding.** `app/static/app.css` is a documented brand-neutral placeholder
  token system (see `.claude/skills/frontend/SKILL.md`), pending either the `maya-math` repo's
  conventions or reference screenshots — see the `design/screenshots/` folder in this repo.
- **Scale-planning beyond POC row counts.** No load testing has been done; the backend/architecture
  review (see session notes) flagged `ship_dataset_to_db`'s full-table-rebuild-under-lock as the
  first thing to strain under concurrent load once the row/dataset count grows well past POC
  scale.

---

## What's already solid — doesn't block going live

These got the most scrutiny during POC development and held up under review (pytest + manual
golden-path + independent QA/backend verification):

- Save-vs-ship separation (autosave never touches the target table; shipping is explicit and
  reconciles every persisted edit across every end user without clobbering).
- Single-row-ownership model (a row has exactly one assigned end user, enforced server-side).
- Three-tier auth (master admin / named admin / end user) with correct role boundaries.
- SQL-identifier-injection defenses (`app/sanitize.py::validate_identifier`) — every dynamically
  built table/column identifier is validated before use in DDL/DML.

These are the foundations; the gaps above are what's needed to carry them into a real
multi-tenant, production deployment.
