# Deploy NagrikOS on Render Free and Vercel

This layout serves the React app from Vercel and FastAPI from Render. [`frontend/vercel.mjs`](../frontend/vercel.mjs) proxies browser requests under `/api` to Render, keeping the browser on one HTTPS origin for Secure, SameSite=Strict session cookies and CSRF. The frontend uses relative `/api` URLs; leave `VITE_API_BASE` unset.

## Before deploying

1. Replace the current Brevo API key if a read-only account check returns HTTP 401. The key in the local ignored `backend/.env` returned **401 on 15 November 2026**; a smoke email was **not confirmed accepted**. [Brevo's transactional API](https://developers.brevo.com/reference/send-transac-email) requires a valid `api-key`, an approved sender, and returns HTTP 201 with `messageId` when it accepts a send. Do not test account emails until that works.
2. Choose the final Vercel production origin, such as `https://YOUR-PROJECT.vercel.app`. Set Render's `PUBLIC_BASE_URL` and `CORS_ORIGINS` to **that exact origin**, with no path or trailing slash. The current local `PUBLIC_BASE_URL` is HTTP localhost and cannot be used in public mode.
3. Make a Neon snapshot and inspect the production branch before any schema or data write. Prefer a disposable Neon child branch for first validation. Keep the local SQLite file and `backend/uploads/` backed up. The production branch was **not** migrated or tested from this workspace.

## Neon schema and existing data

The app refuses to start on PostgreSQL until Alembic revision `20261114_01` is present. Render Free has no [pre-deploy command or shell access](https://render.com/docs/free), so schema changes are intentionally manual:

1. In GitHub, create an environment named `neon-schema` with a secret `DIRECT_URL` containing Neon's **direct**, TLS-enabled URL for the target branch. Use environment protection if this points at production.
2. Run **Actions > Migrate Neon schema > Run workflow** after the Neon snapshot. The workflow runs `alembic upgrade head`. It never runs automatically on push.
3. If existing SQLite data must move, follow [NEON_POSTGRESQL.md](NEON_POSTGRESQL.md) from a trusted Linux/Python host with the SQLite file, `DATABASE_URL` and `DIRECT_URL` for the same branch, and the existing TOTP key. Run the verified copy script before serving traffic. The current Windows host blocks psycopg, so no live data import was done here. The local SQLite database must remain until target counts and relationships are verified.

## Render backend

Create a **Blueprint** from this repository's root [`render.yaml`](../render.yaml), or a Python web service with root directory `backend`, build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and health path `/api/health`. The Blueprint selects the Free plan and Python 3.12.11. [Render's FastAPI guide](https://render.com/docs/deploy-fastapi) documents the equivalent manual setup.

Set these Render environment variables. Keep the values in Render's secret settings, not Git or Vercel:

| Key | Required value |
| --- | --- |
| `NAGRIKOS_MODE` | `public` |
| `COOKIE_SECURE` | `true` |
| `NAGRIKOS_REQUIRE_POSTGRES` | `true`; refuse ephemeral SQLite on Render |
| `DATABASE_URL` | Neon **pooled** TLS URL for the migrated branch |
| `BREVO_API_KEY` | Working Brevo HTTPS API key |
| `MAIL_FROM` | Brevo-approved plain sender email |
| `NAGRIKOS_TOTP_KEY` | Persistent Fernet key; preserve the original if migrating MFA data |
| `PUBLIC_BASE_URL` | Final Vercel HTTPS origin |
| `CORS_ORIGINS` | Same final Vercel HTTPS origin |

`DIRECT_URL` is for migrations only and need not be in Render. Public startup fails closed if required auth/email configuration or the expected Alembic revision is missing. Do not enable demo mode or set a local SQLite path on Render Free.

After schema and data verification, bootstrap **one** real administrator. GitHub's manual **Provision first administrator** workflow uses an environment named `neon-admin` with secrets `DATABASE_URL` (pooled URL), `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_NAME`, and `BOOTSTRAP_ADMIN_PASSWORD`. The password is never a command-line argument. The script refuses to create another admin once one non-demo administrator exists. Remove the bootstrap secrets after the workflow succeeds, sign in, and enable MFA. Later staff use the authorized invitation flow.

After validating the imported records and signing in as the real administrator, run the manual **Disable imported Neon demo credentials** workflow. Add `DIRECT_URL` for the same Neon branch to the protected `neon-admin` environment. This revokes demo sessions and tokens and disables demo passwords and MFA without deleting historical users, complaints, notes, or audit relationships. Public mode already rejects demo logins; this step removes their usable credential material from Neon. Remove the one-time workflow secrets when finished.

## Vercel frontend

Import the same repository into Vercel with **Root Directory = `frontend`**, Framework Preset = **Vite**, Build Command = `npm run build`, Output Directory = `dist`. Set only `NAGRIKOS_RENDER_ORIGIN=https://YOUR-RENDER-SERVICE.onrender.com` as the backend routing variable in the Vercel production environment. Use the exact bare HTTPS origin; `frontend/vercel.mjs` refuses missing/unsafe values and proxies `/api/*` before the SPA fallback. Do **not** set `VITE_API_BASE`, `DATABASE_URL`, `DIRECT_URL`, or `BREVO_API_KEY` in Vercel.

The rewrite disables CDN caching for `/api/*`, and FastAPI adds `Cache-Control: no-store` to API responses. Vercel [documents external rewrites](https://vercel.com/docs/routing/rewrites) as a reverse proxy. Browser cookies should appear on the Vercel origin; verify this on the actual deployment because it cannot be proven from a local build.

## Verify after deployment

1. Open `https://YOUR-RENDER-SERVICE.onrender.com/api/health`, then `https://YOUR-VERCEL-ORIGIN/api/health`. Both should return `{"status":"ok"}`. If Vercel responds with HTML, check its root directory and rewrite variable.
2. Open the Vercel site in a private browser session. The login form must show no demo credentials. Register a citizen, receive the verification email, verify, sign in, refresh the page, and sign out. Check that `nagrikos_session` is Secure, HttpOnly, and host-only for the Vercel origin; `nagrikos_csrf` should be readable to the same-origin client.
3. Request password recovery, verify the generic response for both known and unknown emails, reset the password, confirm old sessions fail, and sign in with the new password. Exercise MFA, a recovery code, and a staff invitation. Check an officer cannot access another department and a citizen cannot read another citizen's case.
4. Confirm the Vercel `/api/auth/me` response and other authenticated `/api` responses are not cached. Check Render and Brevo logs without printing keys or link tokens.

## Free-tier limits

[Render Free sleeps after idle and loses local file changes on restart or redeploy](https://render.com/docs/free). Neon keeps relational records, but this version still stores **uploaded photo bytes locally** under `backend/uploads`. Those bytes are not durable on Render Free, so photo upload should not be used for records that must be retained. Cloud object storage is separate work. The first request after sleep can take about a minute, so signup and login may be slow. Free instances do not provide a shell or pre-deploy migration command. This setup is suitable for a hosted evaluation after the database and email checks; it is not a claim of production durability for attachments.
