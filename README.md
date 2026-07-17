# automation

## Data Ingestion + Correction Rules POC

A proof-of-concept web app for a data-correction workflow:

1. **Admin** ingests data — either upload an `.xlsx` file, or pull a table from an external
   database via a connection string.
2. **Admin** reviews the raw table, picks 4–6 columns to expose to end users, names a target
   database table for corrected output, flags individual cells that need correcting (each with
   its own admin-defined dropdown of valid values), creates end-user accounts, and assigns rows
   to specific end users.
3. **End users** log in and see only the rows assigned to them. Cells the admin didn't flag are
   read-only; flagged cells are dropdowns. Saving writes a full corrected copy of the dataset
   (all rows, only the flagged cells overridden) into the admin-named target table.

Row counts, number of flagged cells, and number of end users are all dynamic — nothing is
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

Then visit `http://localhost:8000/login`.

- Admin login: password only (`ADMIN_PASSWORD` above).
- End-user login: username + password, both set by the admin from the admin panel
  (`/admin`, section "2. End users").

### DB-connector ingestion

Pulling from an external database (`/admin`, "Ingest from DB") uses SQLAlchemy at runtime with
whatever connection string the admin supplies — install the DBAPI driver for that database
first, e.g.:

```bash
pip install psycopg2-binary   # PostgreSQL
pip install pymysql           # MySQL
```

The connection string is used only for the duration of the ingest request; it is never
persisted or logged.

### POC limitations (intentional, by design)

- **Single active dataset**: ingesting new data replaces the current one entirely (raw rows,
  exposed-column selection, cell rules, row assignments, target table setting). The schema is
  structured so multiple concurrent datasets could be added later without a rewrite.
- **No admin directory**: a single shared `ADMIN_PASSWORD` covers all admin access. A real
  admin directory is expected to replace this later.
- **No CSRF token**: acceptable for an internal POC behind `SameSite=Lax` cookies; would need
  addressing before any wider deployment.
- **Target table is fully rewritten on every save** (not appended to), so the target table
  always reflects the latest state of every end user's saved edits, but there's no save
  history.

### Tests

```bash
pytest
```
