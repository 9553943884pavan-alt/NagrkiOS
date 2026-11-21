# Neon testing-branch smoke test

This is a separate, manually dispatched verification step **after** the testing
branch schema was migrated to `20261114_01`. It does not run Alembic, change the
production branch, upload files, use object storage, or touch the Track A ML
workspace. It uses the existing protected `neon-schema` GitHub environment.

## What it checks

1. The pinned testing branch ID, direct host, pooled host, matching database and
   role, and explicit TLS pass `check_testing_target.py` before any connection.
2. A read-only preflight confirms revision `20261114_01` and exactly the 12
   application tables. It records table counts before the test.
3. A session-local PostgreSQL temporary table checks commit persistence and
   rollback behavior. No public table is created.
4. The actual FastAPI routes run against the pooled testing connection. They
   exercise citizen-only signup, email verification, failed unverified login,
   successful login, session refresh, complaint creation/read/update/history,
   officer/admin access, citizen and department isolation, unauthorized access,
   CSRF rejection, and logout. All identities and text are disposable synthetic
   data. Email and password-breach responses are captured locally in memory;
   no mail or external password-check request is sent.
5. Every application database context uses a savepoint in **one outer transaction**.
   Application `commit()` calls are suppressed. The outer transaction is rolled
   back in `finally`, including when an assertion fails. A fresh direct read
   then compares all application table counts and checks that no synthetic user
   remains. If the runner or connection terminates, PostgreSQL also rolls back
   its open transaction. The workflow reports failure if cleanup cannot be
   verified. The temporary table disappears when its session closes.

The API exercises persistence across requests *within* the test transaction.
The temporary table exercises a real PostgreSQL commit and rollback. This does
not prove that committed application rows survive a new connection; proving
that would require a separate approved test with real cleanup risk.

## Manual execution after owner approval

1. In Neon Console, confirm that `testing` is still branch
   `br-hidden-smoke-a7qqswi1`, with direct endpoint
   `ep-curly-term-a7dqknkk.ap-southeast-2.aws.neon.tech`; confirm the backup
   branch `br-damp-mode-a744dvau` is READY. The script cannot verify backup
   readiness itself. Do not select or use the production branch.
2. In GitHub, open **Actions → Smoke test Neon testing branch → Run workflow**.
   Select `main` and enter `br-hidden-smoke-a7qqswi1` as `testing_branch_id`.
   After explicitly approving these testing-branch writes, enter
   `RUN-TESTING-SMOKE` as `approval` and start the run.
3. Approve the `neon-schema` environment deployment using the configured
   reviewer. The five existing environment secrets supply the URLs and pinned
   hosts; no credentials belong in workflow inputs or logs. The workflow and
   migration job share a concurrency group so they cannot overlap.
4. Confirm the job finishes with `Testing smoke PASSED`. A failure reports only
   a sanitized exception class and must be investigated before rerunning. Check
   the testing branch's row counts if cleanup verification failed.

The approval input is an operational acknowledgement, not a substitute for the
owner's explicit permission. **This workflow has not been run against Neon.**
The smoke runner does not need R2 credentials; attachment storage remains a
separate milestone.

## Local verification

Run `python -m pytest tests/test_neon_smoke.py tests/test_testing_target.py -q`
from `backend/`. These tests use dummy URLs and fake connections, and do not
connect to Neon. On Linux or WSL, the Bash gate test also checks that an invalid
approval phrase or branch stops the smoke runner. Full backend regressions use
`python -m pytest tests -q` from `backend/` with no Neon credentials loaded.
