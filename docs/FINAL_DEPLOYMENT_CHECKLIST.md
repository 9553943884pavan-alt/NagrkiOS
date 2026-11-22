# NagrikOS final deployment checklist

**Release status, 21 November 2026:** The first production administrator was created and the one-time workflow retired. The operator later authorized publishing audit fixes to `main` at `ea68b35`; Render reported that deployment successful and Vercel served the matching frontend build. Both `/api/health` endpoints returned HTTP 200. **NOT READY for public traffic:** hosted login/MFA, signup/recovery, role checks and production attachment writes remain unverified. The Sydney schema remains at Alembic `20261114_01`; do not rerun its initial migration. The Singapore production bucket is private and passed a read-only credential check. One Mailjet test reached Gmail Spam and the owner marked it “Not spam.” See the [administrator bootstrap record](ADMIN_BOOTSTRAP_COMPLETION.md) and [follow-up audit](audits/FINAL_REMEDIATION_REPORT.md).

## 1. Preserve the production targets

- Sydney PostgreSQL project `winter-meadow-40329605`, production branch `br-super-glitter-a769u0u1`, pooled TLS URL in Render. Keep the READY pre-migration backup `br-square-sunset-a7thmw2g`. Neon Console previously reported production and backup `protected: false`; review and enable appropriate branch protection before public traffic. A restore from this empty pre-migration backup would remove every later production row and the migrated schema.
- Singapore Object Storage project `cold-violet-69814991`, production branch `br-divine-grass-azierqs7`, private `nagrikos-attachments` bucket, HTTPS endpoint `https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech`. Use this branch's own read/write credentials only. Testing-branch storage credentials and endpoint must never be mixed with production PostgreSQL.
- The production schema and empty application tables were verified at Alembic head `20261114_01`. No application migration runs on startup. The one-time initial production migration workflow was excluded from this release. Future revisions need a new reviewed migration plan and backup.
- Keep `backend/.env` local and ignored. It is not copied into Render, Vercel or GitHub Actions. Back up any legacy SQLite database and `backend/uploads` bytes before a separate approved data cutover; metadata migration alone does not copy attachment bytes.

## 2. Create Render backend and obtain its URL

Use the root `render.yaml` Blueprint, or create a Python web service with these exact settings:

| Setting | Value |
| --- | --- |
| Service name | `nagrikos-api` |
| Plan / region | Free / Singapore |
| Root directory | `backend` |
| Python version | `3.12.11` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |
| Automatic deploys | Off; deploy manually after review |

Render supplies `PORT`; do not set it manually. Record the assigned bare `https://<render-service>.onrender.com` origin. The first startup can fail until the final Vercel HTTPS origin is known and configured; do not substitute an HTTP or guessed public origin. `/api/health` checks the process only and does not prove PostgreSQL, object storage or email delivery. [Render's Blueprint specification](https://render.com/docs/blueprint-spec) documents these settings. [Render warns that Free web services are unsuitable for production applications](https://render.com/docs/free); sleep, restart and availability must be accepted explicitly or a paid service chosen before public traffic.

Set all of the following **in Render only**. Secret values below are placeholders; retrieve each from the approved production source, never from the testing branch. Verify their presence in Render without printing values.

| Render variable | Required value or placeholder |
| --- | --- |
| `PYTHON_VERSION` | `3.12.11` |
| `NAGRIKOS_MODE` | `public` |
| `COOKIE_SECURE` | `true` |
| `NAGRIKOS_REQUIRE_POSTGRES` | `true` |
| `NAGRIKOS_REQUIRE_DURABLE_STORAGE` | `true` |
| `DATABASE_URL` | `<SYDNEY_PRODUCTION_POOLED_TLS_URL>` |
| `NAGRIKOS_TOTP_KEY` | `<PERSISTENT_FERNET_KEY>`; preserve across restarts and data import |
| `MAILJET_API_KEY` | `<APPROVED_MAILJET_PUBLIC_KEY>` |
| `MAILJET_SECRET_KEY` | `<MATCHING_MAILJET_PRIVATE_SECRET>` |
| `MAIL_FROM` | `<MAILJET_ACTIVE_SENDER_ADDRESS>` |
| `OBJECT_STORAGE_BACKEND` | `neon` |
| `OBJECT_STORAGE_BUCKET` | `nagrikos-attachments` |
| `AWS_ENDPOINT_URL_S3` | `https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech` |
| `AWS_REGION` | `ap-southeast-1` |
| `AWS_ACCESS_KEY_ID` | `<SINGAPORE_PRODUCTION_STORAGE_ACCESS_KEY_ID>` |
| `AWS_SECRET_ACCESS_KEY` | `<MATCHING_SINGAPORE_PRODUCTION_STORAGE_SECRET>` |
| `PUBLIC_BASE_URL` | `https://<final-vercel-domain>`; set after Vercel assigns it |
| `CORS_ORIGINS` | The same bare `https://<final-vercel-domain>` origin |

Leave `DIRECT_URL`, `NEON_API_KEY`, legacy `OBJECT_STORAGE_*` credentials, `DATABASE_PATH`, and local demo values out of Render. `DIRECT_URL` belongs only in separately approved schema/admin workflows. Render secrets were not inspected in this review, so **every name above must be confirmed by the owner** before first successful startup.

## 3. Create Vercel frontend and obtain its URL

The deployed Vercel project uses **Root Directory `frontend`**, **Framework Preset Vite**, **Build Command `npm run build`**, and **Output Directory `dist`**. Leave `VITE_API_BASE` unset. Do not put database, Mailjet, storage, MFA or admin secrets in Vercel or any `VITE_` variable. The earlier `NAGRIKOS_RENDER_ORIGIN` instruction is obsolete for the current static configuration.

`frontend/vercel.json` uses static configuration: `/api/*` rewrites to `https://nagrikos-api.onrender.com` before the SPA fallback. The frontend uses relative `/api` paths with same-origin credentials; the production bundle has no demo identity picker. The current Vercel origin is `https://nagrki-os-97.vercel.app`. Keep Render `PUBLIC_BASE_URL` and `CORS_ORIGINS` aligned with that exact HTTPS origin. Verify API/auth responses remain `Cache-Control: no-store` through the proxy before public signup traffic. See [Vercel's static configuration](https://vercel.com/docs/project-configuration/vercel-json) and [external rewrites](https://vercel.com/docs/routing/rewrites).

## 4. Admin bootstrap and authentication

The first real production administrator was created once in [protected run 44916274619](https://github.com/9553943884pavan-alt/NagrkiOS/actions/runs/44916274619). Read-only Neon verification found one user with non-demo `admin` role, one verified administrator, no other users, zero complaints and unchanged Alembic `20261114_01`. The one-time workflow was disabled and deleted; its three `BOOTSTRAP_ADMIN_*` environment secrets were deleted. The `neon-admin` environment, required reviewer, `main` restriction and `DATABASE_URL` remain because the separate protected demo credential cleanup workflow uses the URL. See the [completion record](ADMIN_BOOTSTRAP_COMPLETION.md). Do not recreate or rerun the one-time bootstrap.

Sign in through the Vercel origin as that real administrator, enroll MFA using the persistent Fernet key, store recovery codes securely, sign out and sign back in to verify MFA. Invite staff through the authorized admin flow. If imported demo users exist, only after validating imported records run the guarded **Disable imported Neon demo credentials** workflow with matching production `DIRECT_URL` and `DATABASE_URL`; otherwise do not dispatch it. Public mode already rejects demo logins, but disabling imported credential material is a separate cleanup step.

## 5. Acceptance checks after a separately authorized deployment

Run these through the actual Vercel HTTPS origin in a private browser session and preserve only sanitized evidence:

1. `GET /api/health` directly on Render and through Vercel returns JSON `{"status":"ok"}`. A green health response is insufficient: separately inspect startup logs for the expected Alembic revision and storage configuration, with no secrets.
2. Verify `/api/*` returns backend JSON, never SPA HTML; deep links refresh correctly. Confirm HTTPS, no mixed content, correct `PUBLIC_BASE_URL`, and no browser-visible demo credentials or backend secrets.
3. Register one approved citizen, receive and verify the email, sign in, refresh, and sign out. Verify host-only `Secure`, `HttpOnly`, `SameSite=Strict` session cookie; readable CSRF cookie and same-origin CSRF header. API/auth responses must be `Cache-Control: no-store` and not cached by Vercel.
4. Compare known and unknown recovery responses, complete one approved password reset, verify the old password and sessions fail, and exercise MFA enrollment, challenge, one recovery code and staff invitation. The recovery send runs in-process after the HTTP response; monitor failures and do not assume a durable queue.
5. Create and read a case as a citizen. With separate approval for a controlled production attachment write, upload and download a synthetic image through the authorized API; verify wrong-user, wrong-department and anonymous denial, private direct-bucket access, byte integrity and restart persistence. No production attachment write was authorized for this preparation task.
6. Confirm admin and officer scope, no cross-citizen case access, and no demo login. Check Mailjet message activity and the recipient mailbox for signup/recovery deliverability; the earlier single test reached Gmail Spam and does not validate these flows.

## 6. Monitoring, rollback and incident response

- Monitor Render startup/restarts, 5xx, DB connection failures, storage failures, auth error rates, Mailjet rejection categories and message activity. Logs must never contain credentials, authorization headers, tokenized links or full provider responses. Treat `/api/health` as a process probe only.
- On a failed release, stop new traffic and perform a reviewed Render/Vercel rollback. Do not run an automatic Alembic downgrade. Inspect production read-only before deciding on any database restore; the pre-migration backup is empty and restoring it would destroy newer data. Preserve the backup branch until a newer verified recovery point exists.
- PostgreSQL and Singapore storage cannot commit atomically. Keep object and DB backups separately, use read-only orphan reconciliation after uncertain upload failures, and review any deletion manually. A Mailjet timeout can be ambiguous; inspect activity before any retry to avoid duplicate messages or invalid links.
- Render Free may sleep or restart; local uploads and background recovery tasks are not durable. A public-service availability decision must account for this limitation.

## 7. Release gate

**Offline preparation — passed on this tree:** full backend `pytest tests -q`: **210 passed, 2 skipped** (one Starlette deprecation warning). The focused production-target, PostgreSQL-path and synthetic-startup checks passed **69 tests** before the final full run. Frontend typecheck and production build passed (2,296 modules transformed); `npm audit --audit-level=moderate` found **0 vulnerabilities**. The Render Blueprint parsed with the expected Singapore region and manual deploy trigger; the exact `0.0.0.0:$PORT` binding and Vercel rewrite/caching configuration passed static assertions. The production bundle scan found no demo login identities, demo password or local API origin. A synthetic public-mode startup used only in-memory placeholder HTTPS values, a patched database initializer and a temporary directory; `/api/health` returned HTTP 200 without connecting to Neon or Mailjet. `backend/.env` is Git-ignored and not tracked; static scanning found only dummy credential patterns in test fixtures, no committed live secret. These checks do not validate hosted behavior.

**Before public release:** confirm the exact Render/Vercel settings and production secret names, review Neon and repository branch protection, and accept or replace Render Free's availability risk. The administrator bootstrap is complete; interactive authentication and attachment checks still require separate verification.

**Before public traffic (GO):** production DB and storage target checks pass; a real administrator with MFA exists; private production attachment and authorization checks pass; deployed browser signup, recovery, session/CSRF, role and case tests pass; transactional emails reach intended mailboxes; monitoring and rollback ownership are established. **Current decision: NOT READY for public traffic** because these hosted checks, production storage write and deployment settings remain unverified.
