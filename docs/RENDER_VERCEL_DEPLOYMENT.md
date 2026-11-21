# Deploy NagrikOS on Render Free and Vercel

This layout serves the React app from Vercel and FastAPI from Render. [`frontend/vercel.mjs`](../frontend/vercel.mjs) proxies browser requests under `/api` to Render, keeping the browser on one HTTPS origin for Secure, SameSite=Strict session cookies and CSRF. The frontend uses relative `/api` URLs; leave `VITE_API_BASE` unset.

## Before deploying

1. Set the Mailjet public API key, private secret, and validated active `MAIL_FROM` sender in Render. The updated local credentials authenticated and one authorized Send API test was accepted; the owner received it in Gmail Spam and marked it “Not spam.” See [the live verification record](MAILJET_LIVE_VERIFICATION.md). Public signup, recovery and broader deliverability remain untested.
2. Create the Render service to obtain its HTTPS `.onrender.com` origin, even if public startup waits for Vercel configuration. Import the frontend into Vercel with that Render origin as `NAGRIKOS_RENDER_ORIGIN`. The first successful Vercel deployment assigns a production `.vercel.app` domain. Set Render's `PUBLIC_BASE_URL` and `CORS_ORIGINS` to **that exact HTTPS Vercel origin**, without a path or trailing slash, then manually deploy Render. Never copy a local HTTP origin into public mode.
3. The Sydney `production` branch was migrated and independently verified at Alembic revision `20261114_01` on 21 November 2026: 12 empty application tables plus `alembic_version`. Its READY pre-migration backup is `br-square-sunset-a7thmw2g`. See [production database setup](NEON_PRODUCTION_DATABASE_SETUP.md). Keep the local SQLite file and `backend/uploads/` backed up.

## Neon schema and existing data

The app refuses to start on PostgreSQL until Alembic revision `20261114_01` is present. Render Free has no [pre-deploy command or shell access](https://render.com/docs/free), so schema changes are intentionally manual:

1. In GitHub, create a protected environment named `neon-schema` with secrets `DIRECT_URL` and `DATABASE_URL` for the existing **testing** branch, plus `NEON_TESTING_BRANCH_ID`, `NEON_TESTING_DIRECT_HOST`, and `NEON_PRODUCTION_DIRECT_HOST` copied from Neon Console. Require human reviewer approval for the environment.
2. The initial testing-branch schema migration was already run from Ubuntu WSL after owner authorization. For future revisions only, use **Actions > Migrate Neon schema > Run workflow** with the verified testing branch ID and a recoverable rollback point. The workflow checks the branch ID and URL host pair before `alembic upgrade head`; it never runs automatically on push. The offline check cannot independently prove the Console mapping, so compare it manually.
3. Validate schema, FastAPI authentication, complaint CRUD and role boundaries on testing. Do **not** import existing SQLite data into either Neon branch in this task. For a later approved data cutover, use [NEON_POSTGRESQL.md](NEON_POSTGRESQL.md) and keep the local SQLite database until counts and relationships are verified.

## Render backend

Create a **Blueprint** from this repository's root [`render.yaml`](../render.yaml), or a Python web service with root directory `backend`, Singapore region, Free plan, Python 3.12.11, build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and health path `/api/health`. The Blueprint disables automatic deploys; use manual deployment after review. [Render's FastAPI guide](https://render.com/docs/deploy-fastapi) documents the equivalent manual setup.

Set these Render environment variables. Keep the values in Render's secret settings, not Git or Vercel:

| Key | Required value |
| --- | --- |
| `NAGRIKOS_MODE` | `public` |
| `COOKIE_SECURE` | `true` |
| `NAGRIKOS_REQUIRE_POSTGRES` | `true`; refuse ephemeral SQLite on Render |
| `DATABASE_URL` | Neon **pooled** TLS URL for the migrated branch |
| `NAGRIKOS_REQUIRE_DURABLE_STORAGE` | `true`; Render refuses startup without private object storage settings |
| `OBJECT_STORAGE_BACKEND` | `neon` |
| `OBJECT_STORAGE_BUCKET` | Private production bucket `nagrikos-attachments` |
| `AWS_ENDPOINT_URL_S3` | Singapore production endpoint `https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech` |
| `AWS_REGION` | `ap-southeast-1` |
| `AWS_ACCESS_KEY_ID` | Production storage-branch credential ID |
| `AWS_SECRET_ACCESS_KEY` | Matching production storage-branch secret |
| `MAILJET_API_KEY` | Mailjet public API key |
| `MAILJET_SECRET_KEY` | Mailjet private API secret |
| `MAIL_FROM` | Mailjet-validated active plain sender email |
| `NAGRIKOS_TOTP_KEY` | Persistent Fernet key; preserve the original if migrating MFA data |
| `PUBLIC_BASE_URL` | Final Vercel HTTPS origin |
| `CORS_ORIGINS` | Same final Vercel HTTPS origin |

`DIRECT_URL` is for migrations only and need not be in Render. Public startup fails closed if required auth/email configuration or the expected Alembic revision is missing. Do not enable demo mode or set a local SQLite path on Render Free.

The first real administrator was created through [protected run 44916274619](https://github.com/9553943884pavan-alt/NagrkiOS/actions/runs/44916274619). A read-only production query confirmed exactly one non-demo administrator and unchanged schema revision `20261114_01`. The one-time provisioning workflow was disabled and removed from `main`; its three `BOOTSTRAP_ADMIN_*` secrets were deleted. The `neon-admin` environment, required reviewer and `main` restriction remain. Preserve its `DATABASE_URL` while the separate protected demo credential cleanup workflow uses it. See the [bootstrap completion record](ADMIN_BOOTSTRAP_COMPLETION.md). Do not re-enable one-time provisioning for routine administration. Sign in through Vercel, enroll and verify MFA, and use administrator-authorized staff invitations after password reauthentication for later staff.

If demo accounts were imported, after validating the imported records and signing in as the real administrator, run the manual **Disable imported Neon demo credentials** workflow. Add `DIRECT_URL` for the same production branch to the protected `neon-admin` environment. This revokes demo sessions and tokens and disables demo passwords and MFA without deleting historical users, complaints, notes, or audit relationships. Public mode already rejects demo logins; this step removes their usable credential material from Neon. Remove the one-time workflow secrets when finished.

## Vercel frontend

Import the same repository into Vercel with **Root Directory = `frontend`**, Framework Preset = **Vite**, Build Command = `npm run build`, Output Directory = `dist`. Set only `NAGRIKOS_RENDER_ORIGIN=https://YOUR-RENDER-SERVICE.onrender.com` as the backend routing variable in the Vercel production environment. Use the exact bare HTTPS origin; `frontend/vercel.mjs` refuses missing/unsafe values and proxies `/api/*` before the SPA fallback. Do **not** set `VITE_API_BASE`, `DATABASE_URL`, `DIRECT_URL`, `MAILJET_API_KEY`, or `MAILJET_SECRET_KEY` in Vercel.

The rewrite disables CDN caching for `/api/*`, and FastAPI adds `Cache-Control: no-store` to API responses. Vercel [documents external rewrites](https://vercel.com/docs/routing/rewrites) as a reverse proxy. Browser cookies should appear on the Vercel origin; verify this on the actual deployment because it cannot be proven from a local build.

## Verify after deployment

1. Open `https://YOUR-RENDER-SERVICE.onrender.com/api/health`, then `https://YOUR-VERCEL-ORIGIN/api/health`. Both should return `{"status":"ok"}`. If Vercel responds with HTML, check its root directory and rewrite variable.
2. Open the Vercel site in a private browser session. The login form must show no demo credentials. Register a citizen, receive the verification email, verify, sign in, refresh the page, and sign out. Check that `nagrikos_session` is Secure, HttpOnly, and host-only for the Vercel origin; `nagrikos_csrf` should be readable to the same-origin client.
3. Request password recovery, verify the generic response for both known and unknown emails, reset the password, confirm old sessions fail, and sign in with the new password. Exercise MFA, a recovery code, and a staff invitation. Check an officer cannot access another department and a citizen cannot read another citizen's case.
4. Confirm the Vercel `/api/auth/me` response and other authenticated `/api` responses are not cached. Check Render and Mailjet logs without printing keys or link tokens.

## Free-tier limits

[Render Free loses local file changes on restart or redeploy](https://render.com/docs/free) and Render cautions against using Free services for production applications. The backend requires durable private storage before public startup. The application uses Singapore Neon Object Storage, a separate project from the Sydney database; its production bucket and credentials passed read-only verification, but production attachment writes and authorized downloads remain untested. Local `backend/uploads` remains for development and legacy reads only; attachment bytes are not transferred by the SQLite database-copy script. Copy and verify existing local bytes separately before cutover. The first request after sleep can be slow. Free instances do not provide a shell or pre-deploy migration command. See [storage setup and verification](OBJECT_STORAGE_INTEGRATION.md) and [deployment readiness](DEPLOYMENT_READINESS.md).
