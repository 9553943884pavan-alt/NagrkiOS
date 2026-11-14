> **Historical record:** This document describes an earlier version. For the current implementation use `AUDIT_V4.md`, `SECURITY.md` and `VALIDATION_V4.md`.

# v3 validation summary

- **Backend tests:** `python -m pytest -q` from `backend`: **19 passed**.
- **Backend Python compilation:** passed.
- **Frontend syntax:** TypeScript `transpileModule` parsed **18** TS/TSX application source files with **zero syntax errors**; this does not perform full type checking.
- **Native React selects:** none remain (`<select>` replaced with `SelectMenu`).
- **Frontend CSS:** parsed without syntax errors.
- **Browser focus CSS:** Chromium headless `page.set_content` + stylesheet computed-style test succeeded. Mouse click inside search input produced `box-shadow: none` and `outline: none`; keyboard Tab focus produced visible `2px` outline on a button.
- **API security:** v2 test suite unchanged, covering CSRF, sessions, ownership, upload restrictions and role isolation.
- **npm registry:** `npm install` failed in the creation environment due to `getaddrinfo EAI_AGAIN registry.npmjs.org`, so React production build and Recharts-v3 integration were **not verified** here.
- **Runtime click tests in React:** not executed here because React dependencies cannot be installed. The Windows laptop manual checklist is in `CHANGES_V3.md`.

After extraction on Windows, run:

```powershell
cd frontend
npm install
npm run build
npm ls recharts esbuild
npm approve-scripts --allow-scripts-pending
```

In another terminal, run `python -m pytest -q` from `backend` using its virtual environment. Then run the functional UI checks in `CHANGES_V3.md`.
