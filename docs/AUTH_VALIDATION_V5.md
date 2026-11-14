# Authentication upgrade validation — 14 November 2026

## Root causes and changes

The old Settings button read `currentPassword` from the separate password-change form, so a user could not discover how to start authenticator setup. The login form asked for an authenticator code before verifying the password. The public-facing UI always prefilled and displayed demo credentials. There was no citizen registration, email verification, recovery, or recovery-code lifecycle.

The focused changes are in `backend/app/account.py`, `auth.py`, `db.py`, and `main.py`; `backend/scripts/migrate_auth_v5.py` and `provision_admin.py`; the React account context, API client, Login, Settings and styles; and the dependency-free `backend/static` account modules. `.env.example`, `README.md`, `docs/AUTH_SECURITY_V5.md`, and this report describe configuration and limits. Existing dashboard, complaint, note, attachment and mock-AI code was not refactored.

New routes: `GET /api/auth/config`, `POST /api/auth/signup`, `/verify-email`, `/forgot-password`, `/reset-password`, `/mfa/challenge`, `/mfa/cancel`, `/staff-invitations`, `/accept-invitation`, and development-only `GET /api/auth/dev-mailbox`. Existing login, password and MFA setup/enable/disable routes now use the new lifecycle and session rotation.

## Executed checks

| Check | Result |
| --- | --- |
| `venv/Scripts/python.exe -m pytest tests -q` from `backend` | **38 passed**, one upstream Starlette `httpx` deprecation warning |
| `python -m compileall -q app scripts` | Passed |
| `node --check` on all three fallback JS modules | Passed |
| `npm.cmd install` | Passed; no dependency change |
| `npm.cmd run typecheck` | Passed |
| `npm.cmd run build -- --configLoader runner` | Passed, 2,296 modules; app 390.63 kB, charts 457.73 kB, no 500 kB warning |
| `npm.cmd ls vite rollup recharts esbuild` | Vite 6.4.6, Rollup WASM alias 4.68.3, Recharts 3.10.1, esbuild 0.25.12 |
| `npm.cmd run dev -- --port 15173 --configLoader runner` with isolated FastAPI on port 18000 | Vite ready; React loaded and called FastAPI through the proxy |
| `npm audit` (user's local PowerShell run after commit `e71ecf5`) | **User reported:** 0 vulnerabilities |
| Plain `npm run build` (user's local PowerShell run after commit `e71ecf5`) | **User reported:** passed, 2,296 modules; app 390.63 kB, charts 457.73 kB, no 500 kB warning |

The assistant also attempted `npm.cmd audit --audit-level=moderate` and plain `npm.cmd run build` inside the restricted sandbox. The advisory endpoint was unreachable there, and esbuild was denied access to `vite.config.ts`; the user-supplied local output above verifies both commands in the intended Windows environment. The user's `npm install` output also reported 115 audited packages and zero vulnerabilities.

The backend tests cover signup and forbidden role payloads, email normalization and uniqueness, unverified login, verification replay, generic recovery responses, reset expiry/replay and session revocation, SMTP delivery and failure with a test transport, public mode fail-closed startup and no seed, breached-password checks with a fake range response, login and sensitive-action throttling, QR/manual-key enrollment, expired/replayed TOTP, challenge expiry and cross-challenge limits, recovery-code single use, factor removal, staff invitation authorization, and the existing citizen/officer/admin case isolation and CSRF tests. Production SMTP and the live breach-check service were not contacted.

Browser automation against an isolated demo database exercised React citizen sign-in, dashboard API loading, Settings' dedicated MFA password field, QR/manual-key display, an incorrect code error, six-digit confirmation, one-time recovery-code display, logout, recovery-code second-factor sign-in, and rejection of a reused recovery code. A final Playwright MCP run also completed mobile citizen signup, email-pending state, verification using the development mail sink, and the new citizen's login. Login and Settings survived a browser reload. With FastAPI stopped, sign-out showed “Service temporarily unavailable. Try again.” and kept the local signed-in state until the server could revoke the session. The fallback UI loaded the same session, showed the MFA-enabled state, completed citizen signup with an email-pending message, and opened recovery with keyboard Enter at a 390 px viewport. A mocked public config rendered blank React login fields with no demo picker or password. The mobile signup and authenticated dashboard had no horizontal overflow at 390 px. Expected unauthenticated `/api/auth/me` 401, deliberate invalid-code 401/422, and missing favicon 404 appeared in the browser console. The local Playwright CLI became unavailable after automatic approval review hit its usage limit, but the available Playwright MCP completed the final browser rerun.

## Database migration

Before testing, a SQLite backup was made at `backend/data/nagrikos_pre_auth_v5_20261114.db`. The migration was first run on a temporary copy of that database. It was then run on the live local database using `scripts/migrate_auth_v5.py`, which created `backend/data/nagrikos.pre-auth-v5.20261114T093647Z.db`. Both migration runs preserved **5 users, 6 sessions, 521 complaints, 3 notes, 929 history rows and 1 attachment** and passed `PRAGMA integrity_check`. A direct comparison of every pre-existing column value against the live pre-migration backup returned true. The user's validation case and changed citizen password were retained; no demo reset was performed.

## Remaining limits

The SMTP test used a local fake transport; live SMTP, HTTPS reverse-proxy behavior, external email delivery and public hosting were not verified. TOTP is not phishing resistant, and loss of both the authenticator and all recovery codes requires an external operator process not implemented in this prototype. The security controls here do not certify production deployment.
