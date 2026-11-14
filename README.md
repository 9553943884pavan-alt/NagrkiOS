# NagrikOS — Civic Grievance Intelligence (Hackathon Prototype)

A **v4 audited and security-upgraded, runnable full-stack demo** of a common intake, routing, and tracking pipeline for citizen grievances. It includes a detailed React dashboard, a FastAPI API, a persistent SQLite database, and deterministic **mock** AI recommendations. All 520 initial grievances are **synthetic**; this is **not** the UP government's Jansunwai or CM Helpline service.

**Two usable frontends:**

- **React / Vite (recommended):** polished admin, desk officer, and citizen workspaces at `http://127.0.0.1:5173` after Node.js dependencies are installed.
- **No-install browser UI:** a separate HTML/CSS/JavaScript frontend served directly by FastAPI at `http://127.0.0.1:8000`. No Node.js setup necessary; this version uses the **same live backend and database**.

## What's new in v4?

This is an audited iteration of the v3 design. It retains the same React colors, sidebar, chart layout and dropdown styling, with more robust backend/frontend integration and strengthened **local-demo** authentication. Main upgrades: Argon2id password hashing and automatic old-hash migration; Settings password change; optional TOTP authenticator-app verification; idle session expiry; better citizen dashboard totals; stricter image validation and EXIF removal; minimized officer roster; more precise mock keyword matching; updated Vite 6.4.6 baseline; and synchronized fallback UI security settings.

Read [`docs/AUDIT_V4.md`](docs/AUDIT_V4.md), [`docs/VALIDATION_V4.md`](docs/VALIDATION_V4.md) and [`docs/ML_SCOPE_V4.md`](docs/ML_SCOPE_V4.md) for the complete test results, limitations and feature scope. **27 backend integration/security tests passed.** The full React npm build and browser clicks must still be verified on your Windows machine because npm registry and browser binaries were unavailable in the creation environment.

**Migrating v3 data:** stop both servers; back up your old `backend/data/nagrikos.db` and `backend/uploads/` before copying them into this folder. The database schema migrates automatically at startup without deleting existing cases. Legacy password hashes upgrade on successful login. Do not copy over any active test database, and back up your TOTP key separately if you enable MFA.

## 1. Quick start in VS Code on Windows

Install **Python 3.11+** and, for the enhanced frontend, **Node.js 20+**. Open this entire extracted folder in VS Code.

**Terminal 1 — backend (required)**

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` to try the **complete no-install fallback UI**, or `http://127.0.0.1:8000/docs` for interactive API documentation.

**Terminal 2 — enhanced React frontend (optional)**

```powershell
cd frontend
npm install
npm run build
npm run dev
```

Open `http://127.0.0.1:5173` and log in. Vite proxies `/api` to port 8000.

If npm reports an unreviewed install script, run `npm approve-scripts --allow-scripts-pending`, review the package/version, and use `npm approve-scripts esbuild` **only if needed** (then `npm rebuild esbuild`). Never approve all scripts just to hide a warning. A funding notice is informational; it needs no fix. Check resolved dependencies using `npm ls recharts esbuild`. **The full React build was not available for verification in the creation environment; run `npm run build` on your Windows laptop.**

> Prefer double-click launchers? Run `scripts/start_backend_windows.bat` and `scripts/start_frontend_windows.bat` from Windows Explorer (or from a terminal). Start the backend first.

## 2. Quick start on macOS / Linux

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For the enhanced UI, open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The no-install UI works on port 8000 even when `npm install` is unavailable.

## 3. Demo credentials

All freshly seeded accounts initially use password **`demo123`**. You can change each password in Settings; then only the new password works. Optional authenticator verification adds a second sign-in step.

| Role | Email | What it can do |
| --- | --- | --- |
| Administrator | `admin@demo.in` | Dashboard, all grievances, department analytics, exports, data reset |
| Desk officer | `officer@demo.in` | Department-only dashboard and queue; update cases, notes and same-department assignments |
| Water officer | `water@demo.in` | Water Supply & Sanitation department queue only |
| Health officer | `health@demo.in` | Health & Family Welfare department queue only |
| Citizen | `citizen@demo.in` | Submit complaints and view **only their own** cases and public notes |

Passwords are demonstration-only and the login system must **not** be exposed on the public Internet.

## 4. Working features

| Feature | Works? | Notes |
| --- | --- | --- |
| Login with revocable HttpOnly sessions, Argon2id, optional TOTP, CSRF and role-aware screens | Yes | Localhost demo; change public starter passwords in Settings |
| 75 UP districts and 11 illustrative departments | Yes | Static metadata, not verified official routing |
| Typed Hindi / English grievance | Yes | Stored in SQLite |
| Complaint ticket generation | Yes | `UP-YYYY-XXXXXX` format |
| Category, routing, urgency and ETA suggestions | Simulated | Transparent keyword-based logic; not an ML model |
| Similarity preview | Simulated | Python `SequenceMatcher` on stored same-category cases |
| Photo upload and viewing | Yes | PNG/JPG/WEBP, up to 5 MB |
| Photo content recognition | **No** | Mock logic reads **filename hints only**, not image pixels |
| Browser speech input | Conditional | Web Speech API; browser may use external speech services; no guaranteed Awadhi support |
| Work queues / search / pagination / filters | Yes | Backend SQL queries |
| Update status, department, priority, owner | Yes | Officers restricted to department; admins can reroute; changes logged |
| Citizen-visible and internal officer notes | Yes | Role-filtered read access |
| Officer desk and admin-only analytics | Yes | Department-scoped officer home; system-wide admin insights |
| CSV export | Yes | Administrator only |
| Reset sample data | Yes | Admin only; restores the 520 fictional entries |
| External government integration | **No** | No official government APIs or records used |

## 5. Demo flow (5 minutes)

1. Log in as **Administrator**. Open the Overview, Intelligence, and Departments pages to show seeded trends.
2. Open **New grievance** and enter a complaint (for example, an exposed live electrical wire). Click **Analyze grievance** to preview the mock category, urgency, department, and expected target.
3. Submit as Admin or Citizen. Note the generated ticket and show its activity history. Optionally attach a photo; only its **name** influences the mock preview.
4. As an officer, open **My desk** and a case in your department, change status to **In progress**, assign a same-department officer, and add a **public** note. Show that cross-department data is inaccessible.
5. Sign in as **Citizen**, submit another complaint, then track that ticket; demonstrate that other citizens' cases and internal notes are not visible.
6. Return as Admin, search or filter by department, **Export CSV**, and optionally **Reset demo data** from Settings.

## 6. Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Mac/Linux: `./.venv/bin/python -m pytest -q` from `backend`.

API routes are also documented at `http://127.0.0.1:8000/docs`.

## 7. Project map

```text
NagrikOS-Audited-v4/
├── README.md
├── .gitignore
├── .vscode/                  VS Code tasks and recommended extensions
├── scripts/                  Windows and Unix launchers
├── docs/
│   ├── ARCHITECTURE.md        API flow, database, roles and integration points
│   ├── MOCK_AI.md             Exactly what the AI simulation does
│   ├── SECURITY.md            Development-only security limitations
│   └── NEXT_STEPS.md          How to replace demo logic with real models/data
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py            FastAPI endpoints and local frontend routes
│   │   ├── ai.py              Deterministic mock classifier
│   │   ├── data.py            Metadata and synthetic complaint text templates
│   │   ├── db.py              SQLite schema and deterministic seeding
│   │   └── auth.py            Development login/session logic
│   ├── static/                Fully functional dependency-free browser UI
│   ├── tests/                 Automated API integration tests
│   ├── data/                  SQLite created at first boot (not included)
│   └── uploads/               Uploaded photos (not included)
└── frontend/
    ├── package.json
    ├── vite.config.ts         Local /api proxy
    ├── index.html
    └── src/
        ├── components/        Shell, shared UI
        ├── context/           User session
        ├── lib/api.ts         Typed API client
        ├── pages/             Login, dashboard, intake, case file, etc.
        ├── App.tsx
        └── styles.css
```

## 8. Notes

- The application is meant for **local demonstration**, not public deployment or government use.
- The first backend launch creates `backend/data/nagrikos.db` with 520 repeatable synthetic grievances across all 75 districts. Changes persist until you reset or delete that SQLite file.
- Browser speech recognition is experimental; if unavailable, type the complaint instead. It may use a browser vendor's remote ASR even though the backend itself uses no AI APIs.
- Browser sessions use HttpOnly cookies, 12-hour absolute and 30-minute inactivity expiry, CSRF protection and database-backed revocation. Legacy v1/v3 password hashes automatically migrate to Argon2id on login.
- Run **both servers at `127.0.0.1` only**; credentials are deliberately published, and this is not suitable for public deployment.
- Before upgrading a v1 project with local data, **back up `backend/data/nagrikos.db` and `backend/uploads/`**. Browser login must be repeated after the upgrade.
- See `docs/CHANGES_V3.md`, `docs/CHANGES_V2.md`, and `docs/VALIDATION.md` for fixes, validation, and tested limitations.
- The React UI requires `npm install` once on a machine with package registry access. The self-contained fallback UI avoids that dependency entirely.
- See `docs/SECURITY.md` before sharing access beyond your own machine.
