# NagrikOS v4 architecture

```text
  Citizen React UI        Officer React UI       Administrator React UI
  (submit and track)      (department desk)      (state-wide oversight)
            \                  |                   /
                  Vite same-origin /api proxy
                              |
                   FastAPI + Cookie/CSRF guard
                              |
                     Role/ownership checks
                              |
             SQLite data + sessions + photo ownership
                              |
               Mock heuristic classification engine
```

The React app (`localhost:5173`) and the dependency-free UI (`localhost:8000`) use the same API and SQLite database. Neither frontend is trusted to enforce permissions; the API checks every request.

## Role separation

| Capability | Citizen | Department officer | Admin |
|---|---|---|---|
| Submit, view own grievances | Yes | No new filing | Yes |
| List cases | Own only | Assigned department only | All |
| Update priority, status and notes | No | Own department only | All |
| Route between departments | No | No | Yes |
| Assign owner | No | Same-department officers | Same-department officers |
| Dashboard | Own submissions | Department desk | Global overview |
| Intelligence, departments, CSV export | No | No | Yes |
| Reset all sample data | No | No | Yes |

## Data tables

- `users` — seeded identities with Argon2id password hashes, encrypted TOTP settings and optional pending enrollment; older hashes upgrade at login.
- `sessions` — SHA-256 hashed opaque session secrets, hashed CSRF secrets, absolute/idle expiry, user reference.
- `login_attempts` — hashed account/IP identifiers and timestamps for throttling.
- `complaints` — fictional initial cases, plus locally created ones.
- `history` and `notes` — audit history and public/private case follow-ups.
- `attachments` — uploader ownership, linked complaint ID and original filename; photo bytes stored privately under `backend/uploads`.

Account self-service routes: `GET /api/auth/security`, `POST /api/auth/password`, `POST /api/auth/mfa/setup`, `POST /api/auth/mfa/enable`, `POST /api/auth/mfa/disable`. Citizen overview is `GET /api/citizen/overview` with database-accurate counts.

## Key API routes

| Route | Who can call |
|---|---|
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` | Login publicly; logout with CSRF, me with session |
| `GET /api/meta`, `GET /api/health` | Public metadata / health |
| `POST /api/ai/analyze` | Authenticated; similar cases restricted to role scope |
| `POST /api/complaints` / `POST /api/attachments` | Citizen and admin |
| `GET /api/complaints`, `GET /api/complaints/{id}` | Scoped to role/department/owner |
| `GET /api/attachments/{filename}` | Uploader if unlinked, otherwise authorized case viewers |
| `PATCH /api/complaints/{id}`, `POST /api/complaints/{id}/notes` | Scoped officers and admin |
| `GET /api/officer/overview`, `GET /api/users/officers` | Officer-only department home; officer list for officer/admin (scoped) |
| `GET /api/dashboard`, `/api/insights`, `/api/departments`, `/api/export/complaints.csv` | Admin only |
| `POST /api/admin/reset-demo` | Admin only; also invalidates all active sessions |

The AI adapter is still `backend/app/ai.py` with deterministic heuristic outputs. No production model is bundled. `docs/MOCK_AI.md` explains exactly what is simulated.
