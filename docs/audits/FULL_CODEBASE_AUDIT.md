# Full codebase audit

**Date:** 21 November 2026 (Asia/Kolkata). **Baseline:** `cdfa02a7d43e478da49b16a5e43dba070cc003cb`. The original audit used isolated tests and read-only hosted checks. During the subsequent publication pass, the operator authorized a push to `main`; commit `ea68b3594cd25414a934815da07cffad0afaa7d8` was published and hosting automation deployed it. The follow-up batch later merged at `e8c8d7dbe9de679a3d6f0533b2df2cf88463eb54` and its Render deployment succeeded. The findings table below records the original audit's validation state; current status is in [the task board](AUDIT_TASK_BOARD.md). No production data, secrets, or cloud settings were changed directly.

The repository was inventoried across `frontend`, `backend`, `.github/workflows`, deployment configuration, and existing documentation. Specialist reviews covered frontend behavior and visuals; API, database, and storage; infrastructure and integrations; and an independent QA pass. This is an evidence-based audit of tested paths, not a claim that every visual state or production integration was exercised.

## Prioritized matrix

| Area | Priority | Result |
| --- | --- | --- |
| Access control, authentication, CSRF, IDOR/BOLA | P0/P1 | Existing negative tests passed; no confirmed new bypass; hosted authenticated flows untested |
| Complaint and attachment integrity | P1/P2 | One attachment claim race fixed and tested |
| Demo reset and account state | P2 | Pending invitation foreign-key failure fixed and tested |
| Browser layout, routing and state | P2 | Login and New Grievance 320 px overflow and case-list defects fixed; broader route visuals incomplete |
| CI and production guards | P1/P2 | Destructive manual workflow intent guard added locally; existing environment review retained |
| Dependencies and performance | P1/P2 | Pillow and cryptography updated to patched releases; full local npm/Python audits clear; initial chart preload removed |

## Finding ledger

| ID | Severity | Root cause and reproduction | Files | Fix commit | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| F-01 | P2 | Two complaint requests could read the same unclaimed photo; the second could overwrite its `complaint_id` after the first read. | `backend/app/main.py`, `backend/tests/test_security.py` | `c0366c7` | Forced intervening claim returns 409 and rolls back new complaint; backend suite 220 passed, 2 skipped | Fixed locally; validated |
| F-02 | P2 | Demo reset deleted users while pending staff invitations still referenced an inviter. | `backend/app/db.py`, `backend/tests/test_security.py` | `c0366c7` | Reset with pending invitation succeeds and clears it; backend suite 220 passed, 2 skipped | Fixed locally; validated |
| F-03 | P2 | Global 360 px minimum width forced horizontal overflow at 320 px. | `frontend/src/styles.css` | `c0366c7` | Browser `scrollWidth` 360 before, 320 after; screenshots in frontend QA artifacts | Fixed locally; validated on login |
| F-04 | P2 | Case-list state and semantics: officer action led to a redirect, All cases left filters active, stale responses could replace newer results, and table rows lacked native link behavior. | `frontend/src/pages/Cases.tsx`, `frontend/tests/cases-smoke.js` | `c0366c7` | Synthetic Playwright queue smoke passed all four assertions | Fixed locally; validated with fixtures |
| F-05 | P2 | Manual demo credential cleanup lacked an explicit intent phrase before a destructive job. | `.github/workflows/disable-neon-demo.yml`, `backend/tests/test_production_target.py` | `c0366c7` | Targeted workflow tests 64 passed; actionlint 1.7.12 passed all three workflows; guard precedes install | Published; workflow not dispatched |
| F-06 | P2 | Forced Vite chart chunk was preloaded on the initial HTML even when chart pages were unused. | `frontend/src/App.tsx`, `frontend/vite.config.ts` | `c0366c7` | Build HTML no longer preloads charts; initial HTML-referenced JS gzip 247.52 to 117.65 KB | Fixed locally; build validated |
| F-07 | P1 | `Pillow<13` retained 12.3.0 despite critical/high decoder advisories; uploads are decoded by Pillow. `cryptography<49` also retained advised 48.0.1. | `backend/requirements.txt`, `backend/app/main.py` | `c0366c7` | Upgraded local venv to Pillow 13.0.0 and cryptography 50.0.2; restricted accepted decoders; 220 tests passed, 2 skipped; `pip-audit` 0/51 after update | Published; later successful Render build log confirms both versions; runtime imports unverified |
| F-08 | P2 | Citizen New Grievance voice controls extended to 326 px at a 320 px viewport. | `frontend/src/styles.css`, `frontend/tests/new-viewport-smoke.js` | `c0366c7` | Independent before measurement 326/320; after synthetic browser check 320/320, 390/390, 768/768, 1024/1024; screenshots | Fixed locally; validated |

## Residual and suspected issues

- **P1 release control:** The most recent repository/Neon review recorded unprotected `main` and production database branch. This audit did not change or recheck those cloud rules. Treat them as unresolved for a public launch.
- **P1 release verification:** The most recent bootstrap record showed an administrator but did not verify interactive sign-in or MFA enrollment. Current MFA state was not queried in this audit.
- **P2 transactional delivery:** Mailjet is called before database commit during signup, password reset, staff invitation and reset delivery. If commit later fails, a delivered link or notification may not match committed state. An outbox requires a separately designed change.
- **Operational blocker:** The protected demo credential cleanup workflow requires `DIRECT_URL`; the last environment-secret review found only `DATABASE_URL`. A future dispatch fails closed until the target is separately configured and approved.
- **Unverified:** Runtime Python package imports, authenticated hosted browser flows, current Mailjet delivery, private object storage and live database writes, Firefox/WebKit, full WCAG 2.2 conformance, LCP/INP/CLS field metrics, and all route/state combinations. A later successful Render build log confirms Pillow 13.0.0 and cryptography 50.0.2 were installed. Local `npm audit` reported zero advisories; local `pip-audit` reported zero across 51 installed packages after the dependency update.

The original fixes were published to `main` in the authorized follow-up. GitHub reports the Render deployment for `ea68b35` succeeded, and the hosted Vercel page references the same JS asset hash as the local release build. The later merged deployment's build log confirms the two patched library versions, but does not establish runtime imports or authenticated end-to-end behavior. Follow-up findings and release gates are in `FINAL_REMEDIATION_REPORT.md`.

## Reference standards

[OWASP Top 10:2025](https://top10.owasp.org/), [OWASP API Security Top 10:2023](https://api-security.owasp.org/editions/2023/en/0x11-t10/), [ASVS 5.0](https://asvs.owasp.org/), [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots), and [Core Web Vitals](https://web.dev/articles/vitals).
