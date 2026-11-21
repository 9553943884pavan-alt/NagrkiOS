# Neon PostgreSQL setup and SQLite migration

**Historical testing and data-copy guide.** Both Sydney `testing` and `production` branches now have Alembic revision `20261114_01`. The production branch was migrated and verified on 21 November 2026; its READY pre-migration backup is `br-square-sunset-a7thmw2g`. Do **not** rerun the initial migration. Use [production database setup](NEON_PRODUCTION_DATABASE_SETUP.md) and the [final deployment checklist](FINAL_DEPLOYMENT_CHECKLIST.md) for current release actions. The application uses pooled `DATABASE_URL` for runtime queries; direct `DIRECT_URL` is only for separately approved schema or data-copy work. Keep full URLs in the Git-ignored `backend/.env` or a deployment secret store, never React variables or Git.

## Get the two URLs

1. Open the Neon Console, organization `org-ancient-cloud-73457506`, project `winter-meadow-40329605`. Select the existing `testing` branch and record its branch ID and direct endpoint hostname. Separately record the `production` branch direct endpoint hostname. Do not create or reset branches for this task.
2. With `testing` selected in **Connect**, select its database and role. Copy the connection string with **Connection pooling on** as `DATABASE_URL`. Its hostname has `-pooler`.
3. Turn **Connection pooling off** in the same dialog and copy the direct string as `DIRECT_URL`. Use the same database and role. Keep Neon's TLS parameters (`sslmode=require` and, if supplied, `channel_binding=require`).
4. For a **local** preflight, put both URLs in Git-ignored `backend/.env` and load that file into the terminal's process environment. For the **GitHub migration workflow**, add the URLs separately as `DIRECT_URL` and `DATABASE_URL` secrets in the protected `neon-schema` environment; GitHub cannot read your local `.env`. For **Render runtime**, set only the pooled `DATABASE_URL` there. Never set either URL in Vercel. The app does not silently load `.env`.

For any future testing-branch migration, set `NEON_TESTING_DIRECT_HOST` and `NEON_PRODUCTION_DIRECT_HOST` to the exact direct endpoint hostnames observed in their respective Neon Console branch Connect dialogs. Run `python scripts/check_testing_target.py` from `backend`. It checks the pooled/direct pair, TLS, same role/database, and that the direct host is the verified testing host rather than the production host. This is an **offline URL guard**, not independent proof of branch identity. Confirm the branch ID and endpoint mapping in Neon Console, obtain owner approval, and verify a fresh recoverable rollback point before a future revision.

Do not use the production branch for validation. The copy command refuses any populated target whose rows do not exactly match the SQLite source. Do not run destructive test fixtures or demo reset against either Neon branch.

The requested [Neon prompt](https://neon.com/get-started/prompt.md) was inaccessible from this environment. These steps follow Neon's [Connect guide](https://neon.com/docs/connect/connect-from-any-app) and [pooling guidance](https://neon.com/docs/connect/connection-pooling). Direct connections are used for migrations and data copies because the pooler uses transaction mode.

On Windows machines where Application Control blocks Psycopg's downloaded binary extension, install a trusted PostgreSQL client package that supplies `libpq` (for example, the official PostgreSQL Command Line Tools), or run the backend in a trusted Linux environment. Psycopg's [installation guide](https://www.psycopg.org/psycopg3/docs/basic/install.html) documents its pure-Python implementation with a system `libpq`. Do not disable the host policy. Verify `venv\Scripts\python.exe -c "import psycopg"` before attempting migration. This is a host prerequisite, not a database schema change.

## Validate and copy

Stop writers to SQLite before a real cutover. Back up `backend/uploads/` separately; existing photo bytes remain local until independently copied and verified in a private bucket. Preserve the SQLite database and the **same** persistent `NAGRIKOS_TOTP_KEY` used for existing encrypted MFA values. If the local key was in `~/.nagrikos/totp.key`, copy that key securely into the production secret store. A wrong key aborts migration.

From `backend` in PowerShell, load the local environment file for the current terminal (do not print the values):

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object {
  $name, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($name, $value.Trim('"').Trim("'"), 'Process')
}
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe scripts\check_testing_target.py
# This example performs URL validation only. Do not rerun the initial migration.
```

On a trusted Linux runner, the protected [manual schema workflow](../.github/workflows/migrate-neon.yml) can perform future upgrades after its testing branch ID matches the protected secret and the URL guard passes. The initial revision was already applied directly from Ubuntu WSL after the owner's command. A read-only SQL check confirmed `SELECT version_num FROM alembic_version;` equals `20261114_01`, all 12 application tables (`users`, `sessions`, `login_attempts`, `mail_outbox`, `account_tokens`, `auth_challenges`, `recovery_codes`, `staff_invitations`, `complaints`, `history`, `notes`, `attachments`), columns matching the models, and 13 foreign keys. FastAPI public-mode startup and `/api/health` passed against the testing pooled URL using synthetic local-only email settings. Signup/verification, password reset, login/MFA, complaint and note CRUD, attachment authorization, logout/expired-session rejection, and cross-role access denial have **not** yet been exercised on live PostgreSQL. Do not run SQLite fixtures or demo reset against Neon.

For rollback, stop the test service and restore an approved testing-branch recovery point through Neon. The initial revision intentionally has no destructive `downgrade`; **do not run manual DROP TABLE commands**. Confirm the restored branch and its endpoint mapping before reusing connection URLs. Establish a fresh recoverable point before any future schema write. A restore may change branch identity or endpoint mapping, so recheck them in Neon Console.

The copy command makes a timestamped SQLite snapshot before any target writes, applies additive SQLite upgrades **only to the snapshot**, checks SQLite integrity and foreign keys, copies all 12 application tables in one PostgreSQL transaction, verifies counts and every row value, and resets generated ID sequences. Existing password hashes, MFA ciphertext, account tokens, sessions, cases, notes, attachments metadata, and histories are copied. A rerun verifies the target exactly and exits; a partial or different target aborts. Source SQLite is never deleted or modified. Foreign keys are enforced during import. Existing uploaded files must remain at `backend/uploads/` until their bytes are independently copied and verified in a private bucket.

Run backend tests and exercise signup, sign-in, MFA, role-scoped CRUD, uploads, and refresh on the **development branch**. Deploy only after validating public configuration, email delivery, HTTPS, CORS, TOTP key, and the API's Alembic revision check. Application startup never performs PostgreSQL DDL or demo seeding. PostgreSQL demo reset is disabled.

The application now has a conditional private S3-compatible object-storage adapter. Its `attachments.filename` random primary key is also the object key; `uploaded_by` and `complaint_id` remain relational ownership metadata. This adds no schema change. Neon Object Storage is unavailable in the Sydney project, so a separate Singapore Neon project now hosts the private production bucket. It passed read-only verification; production object writes remain untested. See [object-storage integration](OBJECT_STORAGE_INTEGRATION.md). Do not treat the SQLite-to-PostgreSQL row copy as a copy of attachment bytes.

If synthetic demo identities are imported in a later approved data cutover, retain their historical links while blocking their login. Public mode already rejects demo login. After validating imported data and provisioning a **non-demo administrator**, use the protected, manual **Disable imported Neon demo credentials** workflow to revoke demo sessions and tokens and replace their password hashes with an unusable sentinel. Its target guard pins the Sydney production branch. It keeps historical user rows for referential integrity and refuses to run without a non-demo administrator. Do not delete linked demo user rows.

## Rollback

If copy fails, its PostgreSQL transaction rolls back; fix the cause and rerun against the same empty branch. If validation fails before cutover, point the app back to SQLite and keep the original file and uploads. After serving new writes on PostgreSQL, switching back to the old SQLite file loses those new writes. Use a Neon branch snapshot or reconcile them before a rollback. Do not remove the SQLite source until PostgreSQL has been verified and a separate retention decision is made.

## Status

Validation on 15 November 2026 (Asia/Kolkata):

- The Git-ignored `backend/.env` contains a matching pooled/direct Neon URL pair, TLS required, public mode, Secure cookies, and a valid persistent MFA key. No credential value was copied into source files.
- The real SQLite source was read without modification. A timestamped snapshot `backend/data/nagrikos.pre-postgres.20261114T183706Z.db` passed integrity and schema checks. Source and snapshot each had 5 users, 6 sessions, 521 complaints, 3 notes, 929 history rows, and 1 attachment. The other six application tables were empty.
- Initial PostgreSQL groundwork passed the isolated backend suite and compiled DDL for all 12 tables. The current email transport and test evidence are in [MAILJET_DEPLOYMENT.md](MAILJET_DEPLOYMENT.md); this earlier count is not a live Neon result.
- No Neon query, schema migration, or data import was performed. Windows Application Control blocked Psycopg's native extension and no system `libpq` is installed. Public startup requires `MAILJET_API_KEY`, `MAILJET_SECRET_KEY`, `MAIL_FROM`, and `PUBLIC_BASE_URL`. PostgreSQL CRUD, authentication, permissions, and record-count checks remain unverified. The URL pair currently targets the production branch, so preserve a Neon snapshot and avoid destructive fixtures if testing there.

Do not treat this local validation as a completed PostgreSQL cutover. Record the Alembic revision, exact target counts, API results, and rollback point after live validation.

**20 November 2026 update:** After the owner's explicit command, Ubuntu WSL Python 3.12.10 connected to the verified `testing` direct endpoint (`br-hidden-smoke-a7qqswi1`) and confirmed zero public tables. `python scripts/check_testing_target.py` passed; `alembic upgrade head` succeeded; `alembic current` returned `20261114_01 (head)`. A read-only check found 12 application tables plus `alembic_version`, exact model column sets, and 13 foreign keys. FastAPI startup and `/api/health` passed on the testing pooled URL with local-only synthetic mail settings. **No snapshot was created**, no SQLite data was imported, no production branch was modified, and no cloud object was created. The initial migration has no automated downgrade, so establish a recoverable branch point before further writes or deployment.
