> **Historical record:** This document describes an earlier version. For the current implementation use `AUDIT_V4.md`, `SECURITY.md` and `VALIDATION_V4.md`.

# Validation report — v2

## Automated tests performed in development environment

- `PYTHONPATH=. pytest -q` in `backend/`: **19 passed**.
- Checks include real SQLite lifecycle, credentials, CSRF, invalid/cross-origin requests, session expiry and logout, failed-login lockout, role isolation, officer queue scoping, admin reroutes, assignment validation, private/uploaded photo ownership, public/private case notes, complaint creation, mock analysis, CSV exports, reset, and fallback asset routes.
- `python -m compileall -q app`: passed.
- `node --check backend/static/app.js`: passed.
- TypeScript compiler `transpileModule` parse of **18 TS/TSX source files**: passed (syntax-only; does not perform full type checking or Vite bundling).
- ZIP archive is checked for corruption before delivery.

## Environment limitations (NOT passed/NOT verified)

- Full frontend production build (`npm install && npm run build`) was **not executed successfully**, because the npm registry was unreachable (`EAI_AGAIN registry.npmjs.org`) in this build environment. Run this on your laptop to validate types, dependencies, and bundling.
- Interactive browser E2E automation was attempted, but Chromium was blocked from browsing the local test server (`ERR_BLOCKED_BY_ADMINISTRATOR` in this environment). Thus interactions in the React browser UI and Web Speech recognition were **not browser-verified here**.
- Microphone recognition depends on Chrome/Edge speech service and internet. Improving live interim display, on-stop handling, and error messages does not guarantee successful transcription in all machines/languages.

## Laptop regression checklist

1. Open `http://127.0.0.1:5173` and sign in as Admin. Confirm dashboard, Grievances, Intelligence, Departments, Export CSV, case detail, and Reset.
2. Sign out and sign in as Officer. Confirm "My desk" and scoped Department queue. Global Intelligence, Departments and CSV Export should be absent/inaccessible; records from other departments must return 404.
3. Sign out and sign in as Citizen. Submit a complaint, run mock AI preview, attach photo, read ticket status; global records and internal notes must not be visible.
4. Test speech: select `en-IN` or `hi-IN`, click Record, speak clearly, observe words **live**, click Stop, review text. If no words appear, inspect the displayed error (permissions/network/language). Browser support and working speech service are necessary.
5. Use Tab to navigate form fields/buttons. Focus should be subtle and visible, not a thick green rectangle.
6. Try leaving the page, refreshing, signing out, and signing back in; cases persist locally, but logout revokes a session.
7. In PowerShell: `cd frontend; npm install; npm run build` and fix any local environment/dependency messages before the hackathon demo.
