# Sydney production PostgreSQL setup

**Historical setup record, 21 November 2026 (Asia/Kolkata):** The sections below describe the state at initial schema migration. Render and Vercel were subsequently deployed, and the first production administrator was created once. See [current deployment checklist](FINAL_DEPLOYMENT_CHECKLIST.md) and [follow-up audit](audits/FINAL_REMEDIATION_REPORT.md) for current gates. The guarded migration was applied after a PostgreSQL 18 rehearsal; do not rerun it.

## Verified infrastructure

| Resource | Identity | Verified state |
| --- | --- | --- |
| Sydney project | `winter-meadow-40329605` | PostgreSQL 18 |
| Production branch | `br-super-glitter-a769u0u1` | READY; direct host `ep-frosty-union-a7d7vufy.ap-southeast-2.aws.neon.tech`; 13 tables after migration |
| Pre-migration backup | `br-square-sunset-a7thmw2g` | READY; parent is production; zero application tables |
| Testing branch | `br-hidden-smoke-a7qqswi1` | 13 tables; untouched |
| Disposable rehearsal | `br-floral-truth-a7f8fv10` | PostgreSQL 18; 13 tables; retained |
| Singapore production storage | `br-divine-grass-azierqs7` | Private `nagrikos-attachments` bucket; read-only bucket check passed |

The backup and production branches report `protected: false`. Preserve the backup and review branch protection in Neon Console. The existing testing backup `br-damp-mode-a744dvau` does not protect production. No Singapore storage object was written during the database migration.

## Migration and live verification

The sole Alembic revision `20261114_01` creates 12 application tables, 13 foreign keys and 10 explicit indexes. `backend/migrations/env.py` selects the production guard only with `NAGRIKOS_MIGRATION_TARGET=production`; unknown targets fail closed. The guard verifies project and branch IDs, production direct and pooled hosts, paired database/role/password, and TLS. It rejects testing, Singapore and ambiguous targets. The testing guard and workflow remain unchanged.

Before writing, read-only Neon API checks confirmed the READY production branch and READY backup with production parentage. A direct PostgreSQL check confirmed version 18 and an empty public schema. The configured Neon Management API key authenticated successfully. The revision was applied twice on the isolated rehearsal branch; the second run was a no-op. The same guarded `alembic upgrade head` was then run once against production. `alembic current` returned `20261114_01 (head)`.

A read-only verifier passed after migration: revision `20261114_01`, 12 application tables, expected columns and keys, 13 foreign keys, 10 explicit indexes, and zero application rows. An independent Neon connector read reported 13 production tables while the backup stayed empty. The migration ran locally, **not** through GitHub Actions.

A controlled synthetic production transaction inserted a citizen, complaint and history record, updated and read the complaint, then rolled back. A separate read-only connection confirmed none of those records persisted. This proves basic schema compatibility and rollback; it is not a complete live authentication or attachment test.

## Future schema changes

The initial production migration is complete. Its one-time GitHub Actions workflow was removed from the deployable release because its empty-schema guard is no longer applicable. Do not rerun the initial migration or use the testing-branch workflow against production. A future Alembic revision needs a separately reviewed procedure, a fresh recoverable production backup, branch identity checks, and explicit owner authorization. No schema migration runs at application startup.

Never place credentials in workflow inputs, `.env.example`, frontend code, commits or logs. Local `backend/.env` is Git-ignored and separate from GitHub Actions secrets.

## Application deployment gate

The ignored local `backend/.env` selects `NAGRIKOS_MODE=public`, requires PostgreSQL and durable storage, and points storage at the Singapore **production** branch and private bucket. The runtime pooled `DATABASE_URL`, mail, MFA and storage credentials remain. The obsolete Brevo key and migration-only `DIRECT_URL`, Neon Management API key and branch-guard settings were removed from this local runtime file after the initial migration; future migration work needs its separately protected credentials. The configured storage credential matched an active production-branch read/write credential, and a read-only bucket HEAD succeeded. No live upload or download was performed.

The project has **not yet been deployed to Vercel**. `PUBLIC_BASE_URL` still uses loopback HTTP and `CORS_ORIGINS` has no production HTTPS origin. Public FastAPI configuration correctly fails closed in this state. A one-process FastAPI startup test passed with a temporary synthetic HTTPS origin supplied only in memory; `/api/health` and `/api/auth/config` returned HTTP 200. That origin was not saved and is not a deployment URL. Mail delivery, browser sign-in and live attachment upload were not tested here.

Deploy the frontend to Vercel to obtain its assigned production `.vercel.app` domain, or attach an approved custom domain. Set Render's `PUBLIC_BASE_URL` and `CORS_ORIGINS` to that exact HTTPS origin, configure the remaining production backend settings there, then verify signup, email, login, authorized attachments and logout. Do not guess a URL.

## Test evidence

| Check | Result |
| --- | --- |
| Backend pytest suite | 190 passed, 3 skipped, 1 warning |
| WSL production/testing guard tests | 92 passed, 1 warning; dummy credentials and fake Alembic |
| Frontend typecheck and production build | PASS; largest chunks 390.69 kB and 457.73 kB |
| `npm audit` | PASS; zero vulnerabilities |
| PostgreSQL 18 rehearsal | PASS; first upgrade created schema, second was a no-op |
| Production Alembic upgrade and `current` | PASS; `20261114_01 (head)` |
| Production schema verifier | PASS; 12 tables, 13 foreign keys, 10 indexes, zero rows |
| Synthetic transaction and rollback | PASS; no test rows retained |
| Production storage bucket HEAD | PASS; no object write |
| FastAPI startup with temporary HTTPS origin | PASS; health/auth config HTTP 200 |
| Public deployment and browser end-to-end | NOT TESTED; no Vercel URL or deployed services |

## Backup and rollback

Retain `br-square-sunset-a7thmw2g` as the empty pre-migration production restore point. If a later deployment or migration fails, stop writes, inspect production read-only and prepare a separate owner-approved restore from that branch. Alembic downgrade is disabled. A restore would remove this schema and any data created after the backup; assess impact before restoring. The rehearsal branch remains for owner review and was not deleted.

**Verdict:** Production **database schema GO**; public application deployment **NO-GO** until the Vercel HTTPS origin, Render configuration and live end-to-end checks are complete.
