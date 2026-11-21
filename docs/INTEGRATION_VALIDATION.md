# Database and storage integration validation

**Historical 20 November testing-phase record.** Sydney production was subsequently migrated, Singapore storage testing completed a live round trip, its production bucket passed read-only checks, and one updated Mailjet message reached the owner's Gmail Spam folder. See [current deployment readiness](DEPLOYMENT_READINESS.md) and [final checklist](FINAL_DEPLOYMENT_CHECKLIST.md). The results below describe the earlier testing phase only.

The owner's initial read-only Neon audit on 2026-11-20 confirmed connection success, empty `production` and `testing` branches, no snapshots, and unavailable Neon Object Storage in Sydney. Later that day, after the owner explicitly requested the commands, this workspace used Ubuntu WSL to migrate **testing only**. Local mock tests and live Neon results are distinguished below.

| Command or check | Actual result |
| --- | --- |
| `backend/venv/Scripts/python.exe -m pytest -q` from `backend/` | **77 passed**, one upstream Starlette deprecation warning |
| `backend/venv/Scripts/python.exe -m pytest -q ml/tests` from repo root | **49 passed**; ML data and review store unchanged |
| `npm.cmd run typecheck` from `frontend/` | **Passed** |
| `npm.cmd run build` from `frontend/` | **Passed** with Vite 6.4.6, 2,296 modules; initial sandbox read denial required an approved local-filesystem rerun; no frontend source changes |
| `npm.cmd audit` from `frontend/` | **0 vulnerabilities** after an approved network rerun; sandbox could not reach the advisory endpoint initially |
| `backend/venv/Scripts/python.exe -c "import psycopg"` | **Failed** locally: Windows Application Control blocked the binary wrapper and no system `libpq` was found |
| Ubuntu WSL `uv` Python 3.12.10, `python scripts/check_testing_target.py` | **Passed** with `backend/.env` loaded privately; branch ID matched owner-supplied `testing` mapping |
| Ubuntu WSL read-only direct PostgreSQL query | **Passed** on testing; zero public tables before migration |
| Ubuntu WSL `alembic upgrade head` | **Passed** on testing; no SQLite import or production write |
| Ubuntu WSL `alembic current` and read-only schema audit | **Passed**: `20261114_01 (head)`, 12 application tables, exact model column sets, 13 foreign keys |
| Ubuntu WSL FastAPI public-mode startup and `/api/health` | **Passed** against testing pooled URL with synthetic local-only email settings; no auth/CRUD writes |
| `tests/test_postgres_path.py` | Offline SQLite/SQLAlchemy/mock checks only; no live PostgreSQL query |
| `tests/test_object_storage_path.py` | Synthetic/mock tests: upload/download API, role scope, input rejection, cleanup, restart with fake store, generic HTTPS S3 config validation, read-only listing and botocore stub; **no live bucket request** |
| `tests/test_testing_target.py` | Synthetic URL checks for exact testing host, separate production host, TLS, pooled/direct pairing and same role/database; **no branch or live database verification** |
| `backend/venv/Scripts/python.exe -m pytest -q tests/test_testing_target.py tests/test_object_storage_path.py` | **14 passed** after the final URL-guard change; one upstream Starlette deprecation warning |

The S3 stub verifies path-style SigV4 configuration and expected Put/Get/Delete parameters without network access. It does not prove that any S3 provider accepts credentials, the bucket is private, or bytes survive a real restart. The code keeps a read-only legacy local-file fallback and a read-only orphan-count audit; no old attachment was copied or deleted. Runtime `DATABASE_URL` rejects a direct Neon endpoint, while migration uses `DIRECT_URL`. The **only live database write** in this WSL run was the authorized initial schema migration on testing. No production write, SQLite import, demo account change, cloud object mutation or ML data operation occurred. No Neon snapshot was created.

The live testing-branch schema and FastAPI startup have passed. Authenticated CRUD, signup/recovery/MFA, role denial, email delivery, and storage remain **unverified against live infrastructure**. Establish a recoverable testing-branch point before further writes. Separately approve/provision a scratch private S3 bucket before real upload/download, cleanup and restart checks. See [integration audit](NEON_INTEGRATION_AUDIT.md), [storage details](OBJECT_STORAGE_INTEGRATION.md) and [deployment readiness](DEPLOYMENT_READINESS.md).
