# Neon PostgreSQL setup and SQLite migration

The application uses `DATABASE_URL` for pooled application queries and `DIRECT_URL` only for Alembic and the one-time data copy. Prefer the same **disposable Neon development branch** for validation. The project and organization IDs are identifiers, not database credentials. Keep full URLs in the Git-ignored `backend/.env` or a deployment secret store; never put them in React variables or Git.

## Get the two URLs

1. Open the Neon Console, organization `org-ancient-cloud-73457506`, project `winter-meadow-40329605`. Create a child branch for migration testing; leave the primary branch untouched.
2. Select the child branch in **Connect**, then select its database and role. Copy the connection string with **Connection pooling on** as `DATABASE_URL`. Its hostname has `-pooler`.
3. Turn **Connection pooling off** in the same dialog and copy the direct string as `DIRECT_URL`. Use the same database and role. Keep Neon's TLS parameters (`sslmode=require` and, if supplied, `channel_binding=require`).
4. Put both in `backend/.env`. This file is ignored by Git. Copy the rest of `.env.example` and set `NAGRIKOS_MODE=public` plus all public-mode settings before starting the API. The app does not silently load `.env`.

If a production branch is deliberately used for validation, inspect its existing tables and take a Neon branch snapshot first. The copy command refuses any populated target whose rows do not exactly match the SQLite source. Never run destructive test fixtures or demo reset against it.

The requested [Neon prompt](https://neon.com/get-started/prompt.md) was inaccessible from this environment. These steps follow Neon's [Connect guide](https://neon.com/docs/connect/connect-from-any-app) and [pooling guidance](https://neon.com/docs/connect/connection-pooling). Direct connections are used for migrations and data copies because the pooler uses transaction mode.

On Windows machines where Application Control blocks Psycopg's downloaded binary extension, install a trusted PostgreSQL client package that supplies `libpq` (for example, the official PostgreSQL Command Line Tools), or run the backend in a trusted Linux environment. Psycopg's [installation guide](https://www.psycopg.org/psycopg3/docs/basic/install.html) documents its pure-Python implementation with a system `libpq`. Do not disable the host policy. Verify `venv\Scripts\python.exe -c "import psycopg"` before attempting migration. This is a host prerequisite, not a database schema change.

## Validate and copy

Stop writers to SQLite before a real cutover. Back up `backend/uploads/` separately; photo bytes remain local. Preserve the SQLite database and the **same** persistent `NAGRIKOS_TOTP_KEY` used for existing encrypted MFA values. If the local key was in `~/.nagrikos/totp.key`, copy that key securely into the production secret store. A wrong key aborts migration.

From `backend` in PowerShell, load the local environment file for the current terminal (do not print the values):

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object {
  $name, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($name, $value.Trim('"').Trim("'"), 'Process')
}
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\alembic.exe upgrade head
venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py --database data\nagrikos.db
```

The copy command makes a timestamped SQLite snapshot before any target writes, applies additive SQLite upgrades **only to the snapshot**, checks SQLite integrity and foreign keys, copies all 12 application tables in one PostgreSQL transaction, verifies counts and every row value, and resets generated ID sequences. Existing password hashes, MFA ciphertext, account tokens, sessions, cases, notes, attachments metadata, and histories are copied. A rerun verifies the target exactly and exits; a partial or different target aborts. Source SQLite is never deleted or modified. Foreign keys are enforced during import. Uploaded files must remain at `backend/uploads/` until object storage is implemented.

Run backend tests and exercise signup, sign-in, MFA, role-scoped CRUD, uploads, and refresh on the **development branch**. Deploy only after validating public configuration, email delivery, HTTPS, CORS, TOTP key, and the API's Alembic revision check. Application startup never performs PostgreSQL DDL or demo seeding. PostgreSQL demo reset is disabled.

The existing synthetic demo identities are retained during import so their linked cases, notes, uploads, and audit history remain valid. Public mode already blocks their login. After validation and after provisioning a **non-demo administrator**, run `venv\Scripts\python.exe scripts\disable_demo_credentials.py` from `backend` to revoke all demo sessions and tokens and replace their password hashes with an unusable sentinel. The script also clears demo MFA material. It keeps the historical user rows for referential integrity and refuses to run without a non-demo administrator. Do not delete linked demo user rows.

## Rollback

If copy fails, its PostgreSQL transaction rolls back; fix the cause and rerun against the same empty branch. If validation fails before cutover, point the app back to SQLite and keep the original file and uploads. After serving new writes on PostgreSQL, switching back to the old SQLite file loses those new writes. Use a Neon branch snapshot or reconcile them before a rollback. Do not remove the SQLite source until PostgreSQL has been verified and a separate retention decision is made.

## Status

Validation on 15 November 2026 (Asia/Kolkata):

- The Git-ignored `backend/.env` contains a matching pooled/direct Neon URL pair, TLS required, public mode, Secure cookies, and a valid persistent MFA key. No credential value was copied into source files.
- The real SQLite source was read without modification. A timestamped snapshot `backend/data/nagrikos.pre-postgres.20261114T183706Z.db` passed integrity and schema checks. Source and snapshot each had 5 users, 6 sessions, 521 complaints, 3 notes, 929 history rows, and 1 attachment. The other six application tables were empty.
- Initial PostgreSQL groundwork passed the isolated backend suite and compiled DDL for all 12 tables. The current email transport and test evidence are in [BREVO_DEPLOYMENT.md](BREVO_DEPLOYMENT.md); this earlier count is not a live Neon result.
- No Neon query, schema migration, or data import was performed. Windows Application Control blocked Psycopg's native extension and no system `libpq` is installed. Public startup requires `BREVO_API_KEY`, `MAIL_FROM`, and `PUBLIC_BASE_URL`. PostgreSQL CRUD, authentication, permissions, and record-count checks remain unverified. The URL pair currently targets the production branch, so preserve a Neon snapshot and avoid destructive fixtures if testing there.

Do not treat this local validation as a completed PostgreSQL cutover. Record the Alembic revision, exact target counts, API results, and rollback point after live validation.
