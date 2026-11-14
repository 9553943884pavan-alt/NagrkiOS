# NagrikOS v4 — End-to-end code audit (14 November 2026)

## Scope
Audited React routes, auth context, API client, custom selects, case CRUD forms, uploads, mock triage, charts, department/citizen/admin dashboards, fallback HTML frontend, FastAPI routes, SQLite queries/migrations, cookie sessions, role permissions and dependency metadata. Tests run on real FastAPI app with isolated SQLite databases. **This is a development audit, not a professional penetration test or a claim that every bug is eliminated.**

## Findings and corrections

| Priority | Finding | Change |
|---|---|---|
| High | Password hashes used older scrypt settings; no way to change password | Added OWASP-minimum Argon2id with automatic legacy PBKDF2/scrypt migration, authenticated password-change endpoint and UI; all sessions revoked on change |
| High | No second factor for privileged demo accounts | Added optional TOTP authenticator enrollment/confirmation, encrypted secrets kept separate from database by default, time-window checking and replay prevention; UI in React and fallback |
| Medium | Sessions had only absolute expiry | Added 30-minute server-side idle expiry on top of 12-hour absolute expiry, and revocation on credential change |
| Medium | React could leave protected UI visible after a 401 | Auth context now handles unauthorized API responses; user state clears; blob downloads surface server errors |
| Medium | Citizen dashboard derived active/resolved counts from first 100 records | Added `/api/citizen/overview` with authoritative DB counts and 5 recent records |
| Medium | Upload validation relied on magic bytes alone | Added Pillow decode/size verification, pixel cap, re-encoding to strip EXIF/GPS camera metadata, owner-/case-scoped retrieval |
| Medium | Officer roster disclosed work email addresses unnecessarily | Minimized roster response to officer ID, name, role and department |
| Medium | Heuristic categorizer/urgency used unsafe substring matching | Latin keyword boundaries prevent false triggering inside unrelated words; safety-critical cases still routed for human review |
| Low | Blank-after-trim notes could be inserted | Added server-side non-whitespace length validation |
| Low | Dependency baseline was older than supported Vite 6 minor | Bumped Vite to 6.4.6 (2026-supported maintenance branch); kept Recharts 3.10.1 and reviewed per-version esbuild install-script approval |
| Low | The standalone fallback UI lacked newer auth controls | Added password change and TOTP management and stale-session handling |
| Low | Case-detail error could remain after retry | Clear prior error state before reloading |
| Low | Fallback HTML had no restrictive content-security policy | Added baseline CSP and security headers; kept inline style attributes for chart bars only |

## Reviewed endpoints and matching screens

| React view | API endpoints | Access |
|---|---|---|
| Login & session | `/api/auth/login`, `/api/auth/me`, `/api/auth/logout` | Login public; session reads authenticated |
| Settings / account security | `/api/auth/security`, `/api/auth/password`, `/api/auth/mfa/setup`, `/api/auth/mfa/enable`, `/api/auth/mfa/disable` | Own account only |
| Admin overview | `/api/dashboard` | Administrator |
| Officer home | `/api/officer/overview` | Officer, own department |
| Citizen home | `/api/citizen/overview` | Citizen, own cases |
| Registry / case details | `/api/complaints`, `/api/complaints/{id}` | Role-scoped |
| New complaint | `/api/meta`, `/api/ai/analyze`, `/api/attachments`, `/api/complaints` | Logged-in citizen/admin for submissions, auth for mock preview |
| Case workflow | `PATCH /api/complaints/{id}`, `POST /api/complaints/{id}/notes`, `/api/users/officers` | Official, department-scoped officer and global admin |
| Analytics | `/api/insights`, `/api/departments` | Admin only |
| CSV report | `/api/export/complaints.csv` | Admin only |
| Reset | `/api/admin/reset-demo` | Admin only, **destructive demo-only** |

## Known limitations and remaining risks

1. **Demo credentials are publicly known** (`demo123`) until changed in Settings. Never expose the instance to the public Internet, use real citizen information, or treat it as production hardened. TOTP is optional and initially off.
2. **SQLite complaint bodies are not encrypted at rest.** OS account permissions protect local files on Unix; Windows ACLs and physical-device security matter. Encrypted MFA seeds are stored in SQLite but rely on a separate encryption key (`~/.nagrikos/totp.key` by default); backup both securely. For production use managed database/encryption and a real KMS.
3. **No independently verified real-world ML** exists here. All seed records are synthetic. No live Jansunwai data or department routing rules are used. No image-pixel classification is done; filename hints are only illustrative, and browser speech may be network-dependent and does not guarantee Awadhi accuracy.
4. Some endpoints allow administrative destructive operations after an authenticated admin session, and the reset restores well-known demo credentials. Disable reset, enforce MFA/SSO, add audit monitoring and reauthentication for production.
5. No external identity verification, official personnel mapping, upload antivirus engine, comprehensive accessibility audit, rate limits on every endpoint, or automatic PII retention/deletion policy.
6. In this environment the npm registry cannot be reached, so the React production build, dependency audit and actual React dropdown/browser-click tests were **not executed**. TypeScript/TSX syntax was verified; Windows commands and manual acceptance checklist are in `VALIDATION_V4.md`.
7. React v3's custom menu uses an accessible role/listbox pattern and CSS portals, but requires real keyboard, screen-reader and responsive-width testing on Windows before any public use.

## Security research

- OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Maintained Vite branches: https://vite.dev/releases
- npm script-approval policy: https://docs.npmjs.com/cli/latest/commands/npm-approve-scripts
