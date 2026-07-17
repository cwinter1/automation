# automation

## Data Ingestion + Correction Rules POC

A proof-of-concept web app for a data-correction workflow:

1. **Admin** ingests data — either upload an `.xlsx` file, or pull a table from an external
   database (a named connection or a raw connection string). Every ingest creates a new,
   independent dataset; nothing is replaced.
2. **Admin** reviews a dataset's raw table, picks 4–6 columns to expose to end users, names a
   target database table for corrected output, flags individual cells that need correcting
   (each with its own admin-defined dropdown of valid values), can add wholly new blank columns
   or rows for end users to fill in, creates end-user accounts, and assigns rows to specific end
   users.
3. **End users** log in and see every row assigned to them, across every dataset they've been
   given rows in. Cells the admin didn't flag/add are read-only; editable cells are dropdowns or
   free text. Changes autosave immediately, but nothing reaches the database until the dataset
   is explicitly **shipped** (by the end user or the admin) — publishing a full corrected copy
   (all rows, only the edited cells overridden) into the admin-named target table.

Row counts, number of datasets, flagged cells, and end users are all dynamic — nothing is
hardcoded.

### Running it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ADMIN_PASSWORD=changeme
export SESSION_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/login`. Three roles:

- **Master admin**: password only (`ADMIN_PASSWORD` above). The only role that can create or
  remove admin accounts (admin panel, section "0. Admins").
- **Admin**: username + password, created by the master admin. Full access to everything in the
  admin panel except managing other admin accounts.
- **End user**: username + password, created by an admin (admin panel, section "3. End users").

### DB-connector ingestion

Pulling from an external database (`/admin`, "Ingest from DB") uses SQLAlchemy at runtime.
Install the DBAPI driver for whatever database you're connecting to first, e.g.:

```bash
pip install psycopg2-binary   # PostgreSQL
pip install pymysql           # MySQL
```

You can either paste a raw connection string, or predefine named connections via environment
variables so the admin can pick a name instead of pasting credentials each time:

```bash
export DB_CONN_PROD="postgresql://user:pass@prod-host/db"
export DB_CONN_STAGING="postgresql://user:pass@staging-host/db"
```

The admin UI's "Named connection" dropdown lists only the *names* (`GET /admin/db-connections`)
— the underlying connection strings never leave the server, and whichever one is resolved for a
given ingest is used only for the duration of that request; it is never persisted or logged.

### Multiple datasets

Every ingest — xlsx or DB — creates a new dataset alongside any existing ones; nothing is ever
replaced or wiped. Give each one a label at ingest time (or accept the auto-generated one), then
use the dataset picker at the top of the admin panel to switch which dataset you're configuring.
An end user's review grid automatically spans every dataset they have rows assigned in.

### Autosave and shipping

End-user edits autosave into the app immediately (so nothing is lost), but that alone does
**not** touch the target database table. Publishing requires an explicit "Ship to DB" action —
available to an end user (for a dataset they have rows in) and to the admin (for any dataset).
Shipping recomputes the target table from *every* persisted edit across *every* end user at that
moment, so two different end users shipping independently accumulate rather than clobber each
other's work.

### POC limitations (intentional, by design)

- **No CSRF token**: acceptable for an internal POC behind `SameSite=Lax` cookies; would need
  addressing before any wider deployment.
- **Target table is fully rewritten on every ship** (not appended to), so it always reflects the
  latest state of every end user's edits at ship time, but there's no ship history.

### Confirmed, not a limitation

A row has exactly one assigned end user — this is permanent by design, not a POC shortcut. Two
end users must never see the same row.

### Tests

```bash
pytest
```
