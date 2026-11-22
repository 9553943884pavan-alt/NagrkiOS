# Regression test results

**Run date:** 21 November 2026 (Asia/Kolkata). All backend tests cleared `DATABASE_URL`, `DIRECT_URL`, Mailjet and object-storage credentials from the test process and set `NAGRIKOS_MODE=demo`. No production database or bucket was used.

## Follow-up publication and remediation pass

Before publishing the original audit commits, the Windows backend suite again returned **220 passed, 2 skipped**; frontend typecheck and WSL build passed. npm audit reported zero advisories, pip-audit reported no known vulnerabilities for the resolved backend requirements, focused Ruff `E9,F63,F7,F82` passed, and checksum-verified actionlint 1.7.12 passed the original three workflows. Broad Ruff reported 140 findings, mostly the documented style backlog; it is not a passing broad-lint gate.

With seven added isolated backend regressions, the full Linux Python 3.12 suite passed **229 tests**. The final Windows run passed **227 tests, 2 skipped**. The Linux run recorded an existing Starlette/httpx deprecation and a local pytest cache-permission warning; Windows recorded the Starlette warning. Both runs removed production database, Mailjet and object-storage credentials from the test process. The new tests cover repeated S3 listing tokens, CSRF/session/role/MFA edges, and ambiguous Mailjet timeout one-attempt behavior. Independent QA reran all seven new tests: **7 passed**. The four-workflow actionlint check passed after adding the non-deploying CI workflow; that workflow has not yet run on GitHub.

Synthetic Chromium browser checks covered **112 authenticated role/route/width loads** (16 states at 320, 375, 390, 768, 1024, 1440 and 1920 px) with zero settled document overflow. Six anonymous account screens covered **42 width loads**, also with zero overflow. A synthetic mobile-menu keyboard test passed focus containment, background inertness, Escape focus restoration and desktop-resize cleanup. Axe-core 4.10.3 at 390 px found **zero A/AA rule violations across all 16 authenticated and six anonymous tested states** after fixes; initially every state had serious contrast findings. These are tested states, not full WCAG conformance. Firefox could not launch in the Windows environment because `lgpllibs.dll` was missing, and WebKit was not installed.

The final anonymous rerun found and verified a same-tab fragment-navigation fix. A separate mocked browser regression passed reset, verify and invitation link navigation, confirmed each request used the current synthetic token, and checked hash removal and a late response (**4 mocked requests, 0 live account actions**). The mobile menu and department native-link keyboard regressions also passed after the final changes.

An earlier warm local built-preview Chromium sample on synthetic admin Overview at 1440 px measured FCP 208 ms, LCP 812 ms and CLS 0.0263. These are lab samples, not hosted or field Core Web Vitals. The final index bundle measured 118.27 KB gzip versus 117.65 KB for the previous audit build.

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
