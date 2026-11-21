# Regression test results

**Run date:** 21 November 2026 (Asia/Kolkata). All backend tests cleared `DATABASE_URL`, `DIRECT_URL`, Mailjet and object-storage credentials from the test process and set `NAGRIKOS_MODE=demo`. No production database or bucket was used.

| Check | Executed result | Limit |
| --- | --- | --- |
| Baseline backend `pytest -q` | 218 passed, 2 skipped; one upstream Starlette/httpx deprecation warning | Before new regressions |
| Final backend `pytest -q` with Pillow 13.0.0 and cryptography 50.0.2 | **220 passed, 2 skipped**; same warning | Isolated local fixtures; no live PostgreSQL/storage write |
| Independent focused `test_api.py`, `test_security.py`, `test_auth_lifecycle.py` | 32 passed | Includes cross-citizen, cross-department, CSRF, MFA replay, staff invitation and new race/reset tests |
| Backend compile | `python -m compileall -q app scripts` passed | Syntax only |
| Ruff high-signal `E9,F63,F7,F82` | Passed | Broad Ruff run found 138 existing style/lint findings; no broad clean claim |
| Frontend `npm.cmd run typecheck` | Passed | TypeScript only |
| Frontend WSL `npm run build` | Passed; Vite 6.4.6 transformed 2,297 modules | Final local build, no deployment |
| `npm audit --audit-level=moderate --json` | Zero advisories among 141 installed dependencies | Local lockfile/install state |
| `pip-audit` of installed backend venv | Initially 60 findings in Pillow, cryptography and local pip; **zero across 51 packages** after updates | Local environment; deployed package versions unverified |
| Synthetic Playwright officer case queue | Passed: officer action hidden, all filters cleared, stale result ignored, native link keyboard navigation | Mocked API; Chromium only |
| Synthetic Playwright citizen New Grievance widths | Passed: document width equals viewport at 320, 390, 768 and 1024 px | Mocked API; Chromium only |
| Independent isolated demo browser check | Citizen dashboard and Cases at 320 px had width 320; New Grievance initially 326 at 320, then fixed and rechecked above | Disposable SQLite and uploads; no real user data |
| Login visual check | 320 px document width 360 before, 320 after; no overflow at 375, 768, 1280, 1920 in specialist checks | Chromium; login route only |
| Workflow lint | Checksum-verified actionlint 1.7.12 passed all 3 workflows; `git diff --check` passed | No GitHub workflow was dispatched |
| Hosted health | Render `/api/health` 200 and Vercel `/api/health` 200, both `{"status":"ok"}` | Read-only; first Render request timed out during cold start, second returned 200 |

The backend suite includes existing Mailjet and object-storage failure-simulation tests. Passing those mocks does not verify current provider delivery or live bucket behavior. No current production-authenticated browser journey, Firefox/WebKit run, axe scan, screen-reader session, LCP/INP/CLS measurement, or live database transaction test was performed.

## Build size comparison

| Metric | Baseline | Local fix |
| --- | ---: | ---: |
| Initial HTML-referenced JavaScript, gzip | 247.52 KB | 117.65 KB |
| Index JavaScript, gzip | 117.38 KB | 117.65 KB |
| Chart shared chunk, gzip | 130.14 KB, preloaded | 113.09 KB, dynamic |

This measures built artifact references and sizes. It does not measure network transfer, LCP, INP or CLS.
