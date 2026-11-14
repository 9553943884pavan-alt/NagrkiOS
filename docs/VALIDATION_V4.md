# NagrikOS v4 — Validation and Windows acceptance checklist

## Verified in build environment

- `python -m pytest -q`: **27 passed** (API workflow, privacy, CSRF, role restrictions, image upload, notes, CSV export, Argon2id migration, password change, TOTP setup/enroll/replay/disable, expiry, reset, mock triage contract).
- `python -m compileall -q backend/app`: passed.
- TypeScript `transpileModule` syntax parse: **18 TS/TSX source files, no syntax errors** (not a full type check).
- `node --check backend/static/app.js`: passed.
- Frontend and fallback CSS parse with `tinycss2`: no stylesheet-level errors.
- API endpoint cross-reference: manually checked frontend API paths against FastAPI routes.
- ZIP packaging and integrity: checked after creation.

## Not verified in build environment

- Registry connectivity: `npm view ...` fails with `EAI_AGAIN registry.npmjs.org`.
- Production React `npm run build` cannot run without installing npm dependencies.
- Chromium browser executable is absent here. The Playwright API is installed but actual React UI clicks / snapshots were not available.
- Consequently, no claim of 0 current npm advisories or warning-free install can be made until you run the checks on your laptop.

## Windows validation run — 14 November 2026

- Backend: **27 tests passed**, with one upstream Starlette `httpx` deprecation warning. Python compilation and `node --check backend/static/app.js` passed.
- Frontend: `npm run typecheck` passed after correcting the dashboard activity type in `frontend/src/types.ts`. `npm audit` found **0 vulnerabilities**; `npm approve-scripts --allow-scripts-pending` found no unreviewed scripts. Resolved versions: Vite 6.4.6, Recharts 3.10.1, esbuild 0.25.12.
- Production build: TypeScript passed. Windows Application Control blocked Rollup's native `rollup.win32-x64-msvc.node` even outside the sandbox. For this validation run only, the matching `@rollup/wasm-node@4.68.3` package was installed without saving it to project dependencies, and the ignored local `node_modules/rollup/dist/native.js` was directed to its WASM implementation. The build then passed outside the sandbox, transforming 2,296 modules. Vite warned that the 846 kB JavaScript bundle exceeds its 500 kB chunk size suggestion. A fresh native build on this machine remains subject to the Application Control policy.
- Browser: React login, Overview, registry, complaint creation with mixed English/Hindi text and a PNG, role-scoped case access, officer notes and status update, admin insights/departments, CSV export, and fallback login/settings/case update were exercised. Overview cards and charts had no overlap or horizontal overflow at 1366, 1024, and 390 px. Dropdown arrows, Escape/outside close, keyboard selection and Tab focus, ticket search, and clearing filters worked. The exported CSV opened with 520 rows before the validation case was submitted.
- Security: Changing the citizen password revoked a second active session (API status 200 before and 401 after); the old password was rejected and the new one accepted. A citizen could see the public officer note but not the internal note. A water officer could not open an unrelated department case; the cross-department control was disabled. Backend tests cover server-side cross-department rejection.
- Remaining hands-on checks: TOTP with a phone authenticator and live Hindi/English microphone dictation were not performed. Browser speech-service behavior remains dependent on the local browser, microphone permission, and network.
- **Validation data retained at the user's request:** the local database now contains 521 cases. Case `UP-2026-000521` has status `in_progress`, priority `medium`, and three validation notes. The citizen demo password was changed during this run. The admin reset was not run.

## Permanent Windows Rollup/Vite fix — 14 November 2026

**Root cause.** The exact `parseAst.js` error came from a prior local edit to `frontend/node_modules/rollup/dist/native.js` that replaced Rollup's exports with `module.exports = require('@rollup/wasm-node/dist/native.js')`. Node's static CommonJS named-export detection could not find `parse` in that file. A clean `npm ci` restored Rollup's original file and eliminated that syntax error. The original build then failed with `ERR_DLOPEN_FAILED`: Windows Application Control blocked the correctly installed `@rollup/rollup-win32-x64-msvc@4.68.3` native module. Rollup and the native package both resolved to 4.68.3, and the installed Vite/Rollup package engine ranges include Node 24. No `.npmrc` or npm setting disabled optional dependencies or install scripts.

**Fix.** `frontend/package.json` now pins `rollup` to the official `npm:@rollup/wasm-node@4.68.3` package as a dev dependency; `frontend/package-lock.json` records the exact artifact and integrity. npm places this package at `node_modules/rollup`, so Vite uses Rollup's maintained, platform-independent distribution without editing installed files or changing app code. The Windows native package was verified before the change; it is absent after a clean install because the WASM distribution replaces it. Rollup documents this distribution as a [drop-in replacement](https://rollupjs.org/migration/), and [npm documents package aliases](https://docs.npmjs.com/cli/v11/using-npm/package-spec/#aliases). No global security setting or install-script restriction was changed.

**Executed checks.** `npm ci` restored a clean dependency tree; `npm install` succeeded; `npm run typecheck` passed; `npm run build` passed after a second clean `npm ci`, transforming 2,296 modules; `npm run dev` started Vite 6.4.6 at `http://127.0.0.1:5173`; `npm audit` reported 0 vulnerabilities; and `npm ls vite rollup recharts esbuild` showed Vite 6.4.6, the pinned Rollup WASM alias 4.68.3, Recharts 3.10.1, and esbuild 0.25.12. Browser testing loaded the React admin dashboard with 521 existing cases and fetched `/api/meta` through Vite's proxy with HTTP 200, 75 districts, and `is_demo: true`.

**Remaining limits.** Windows Application Control still blocks the native Rollup binary on this machine; the project now uses the maintained WASM implementation. The browser logged unauthenticated `/api/auth/me` 401 responses before login and a missing favicon 404; neither prevented the UI or API check. The application UI, backend, authentication, database schema, and app features were not changed for this fix.

## Production chunk warning resolved — 14 November 2026

Vite's previous 846.01 kB JavaScript chunk exceeded its 500 kB per-chunk suggestion. `frontend/vite.config.ts` now uses Rollup's documented [`output.manualChunks`](https://rollupjs.org/configuration-options/#output-manualchunks) option to put Recharts and its dependencies in a separate `charts` chunk. `npm run build` completed without the chunk warning: the app chunk is 386.55 kB and the charts chunk is 457.73 kB. `npm run typecheck` passed. In a browser, the production build served by `npm run preview -- --port 5173` loaded both the admin Overview charts and the Insights chart page using the existing FastAPI connection.

This split addresses the per-chunk warning. The two JavaScript chunks are still loaded for the initial page, so their combined size is essentially unchanged. `npm fund` is an informational notice about package funding, not a build warning or vulnerability.

## Run in Windows PowerShell (VS Code)

On the Windows machine used for the run above, `py -3` could not find the installed Python, so `python` was used. PowerShell blocked the `npm.ps1` shim; use `npm.cmd` in place of `npm` if that happens.

```powershell
# terminal A - backend
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# terminal B - frontend
cd frontend
npm install
npm run typecheck
npm run build
npm audit
npm ls vite recharts esbuild
npm approve-scripts --allow-scripts-pending
npm run dev
```

If npm reports a pending `esbuild` postinstall for a **different resolved version**, review the package and run `npm approve-scripts esbuild` deliberately, then `npm rebuild esbuild`. Never run `--dangerously-allow-all-scripts`. `npm fund` is informational.

## Manual acceptance flow (React at http://127.0.0.1:5173)

1. Login as admin and confirm Overview has charts, totals and no overlapping cards at 1366px, 1024px and ~390px viewport widths.
2. Registry: click the dropdown arrow itself (status, priority, district), select an option; click outside/Escape to close; tab through with keyboard; search for a ticket and clear filters.
3. Complaint: change district using the searchable menu, enter English/Hindi text, preview AI, upload a valid photo, submit, and verify case ticket and status.
4. Settings: change a **non-admin** demo account password to a 12+ character passphrase, verify old sessions stop working, then sign in with the new password.
5. Settings: start TOTP using a phone authenticator, enter current six-digit code; sign out and back in with a **fresh** code (codes are single-use per 30-second period), and disable when done. Keep the setup secret private.
6. Citizen: verify only personally submitted tickets appear and counts are correct; try opening an admin case by URL and confirm access denied.
7. Officer: show department-only queue; add public and internal notes; verify that an unrelated department case is denied and that reassigning cross-department is rejected.
8. Admin: see all departments, insights and CSV export; download CSV and open it; confirm activity logs and case updates persist across refresh.
9. Voice: try Chrome/Edge in Hindi and English with microphone permission; check text *during* dictation and after Stop. Browser-service/network issues must appear as error messages; **Awadhi is not guaranteed**.
10. Open `http://127.0.0.1:8000` to test the fallback login, Settings security controls and basic CRUD separately.

Security check: stop the servers before copying databases between versions, back up `backend/data/nagrikos.db`, and keep the TOTP key file safe if MFA is enabled.
