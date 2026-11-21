# Live Neon testing storage validation

**Date:** 2026-11-21. **Decision: GO for the tested Sydney-testing ↔
Singapore-testing integration only. NO-GO for production deployment.** The
owner supplied Neon Console screenshots showing the Singapore testing branch,
`nagrikos-attachments` marked **Private**, its Storage Connect endpoint, and a
testing-branch credential granted `storage:read` and `storage:write`. The
guarded WSL preflight and one controlled synthetic live
run passed. All test records and objects were removed.

## Approved resources and configuration

| Resource | Expected testing target | Result |
| --- | --- | --- |
| Sydney PostgreSQL project / branch | `winter-meadow-40329605` / `br-hidden-smoke-a7qqswi1` | PASS: existing target guard accepted the pooled and direct hosts, same database and role, and explicit TLS. A read-only connection returned Alembic `20261114_01`. The project/branch mapping relies on the owner's previously verified Neon endpoint mapping; no Neon management API identity check was available in this session. |
| Singapore storage project / branch | `cold-violet-69814991` / `br-lively-base-azf2mt0j` | PASS: the configured endpoint exactly matched `https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech` and a signed read-only `ListObjectsV2` with `MaxKeys=0` succeeded. No existing object names or bytes were read. |
| Bucket | `nagrikos-attachments` | PASS: the owner's Neon Console screenshot shows **Private** on the testing branch. An unsigned read of the test object returned HTTP **403**. The testing-branch Credentials view shows `storage:read` and `storage:write`; the locally configured credential authenticated to the pinned endpoint. The screenshot does not expose enough of the key ID to prove it is the exact local credential. |

`backend/.env` exists and contains the database and AWS storage credential
variables. The repository root has no `.env`. FastAPI does **not** auto-load
either file: the test harness explicitly parses `backend/.env` in memory. That
file currently omits `OBJECT_STORAGE_BACKEND` and `OBJECT_STORAGE_BUCKET`; the
approved, non-secret values `neon` and `nagrikos-attachments` are supplied
only to the test process. Neither `.env` file was modified, and no value or
connection string was printed.

The first Windows read-only database attempt failed with `OperationalError`
before a schema query and with no SQLSTATE. The same guarded read-only preflight
passed from WSL Ubuntu using Python 3.12.10. This is an environment-specific
connection limitation, not evidence of a database schema failure.

## Test record

| Check | Status | Evidence or blocker |
| --- | --- | --- |
| Offline testing-target and storage configuration guards | PASS | Exact testing hosts/endpoint, region and bucket accepted; production or mixed targets rejected by guards. |
| Sydney testing PostgreSQL connection and schema | PASS | Read-only WSL query returned expected Alembic revision. |
| Singapore testing bucket authentication | PASS | Signed `ListObjectsV2` with `MaxKeys=0` succeeded; no object data returned. |
| Bucket PRIVATE access and credential branch association | PASS with limit | Owner screenshots showed **Private** and a testing-branch credential with `storage:read` and `storage:write`; signed testing access worked. Exact local key-ID matching was not independently performed. |
| Synthetic authenticated upload and metadata persistence | PASS | One 2×2 synthetic PNG was uploaded through FastAPI; the matching `attachments` row persisted in Sydney testing PostgreSQL. |
| Authorized and unauthorized downloads | PASS | Owner received HTTP 200; a second synthetic citizen received HTTP 404; anonymous API access received HTTP 401; unsigned direct S3 GET received HTTP 403. |
| SHA-256 image integrity | PASS | Authorized API bytes and signed S3 bytes had equal SHA-256 digests; decoded pixels matched the generated synthetic image. |
| Injected database-write failure and compensating deletion | PASS | The second test upload was forced to fail at the metadata insert; its test-specific object and row were absent afterward. |
| Test-specific database and object cleanup | PASS | Both synthetic users, their sessions, attachment metadata and both predeclared test keys were absent. All 12 application tables returned to zero rows. |
| Read-only orphan reconciliation after cleanup | PASS | `metadata_rows=0`, `private_objects=0`, `objects_without_metadata=0`, `metadata_without_cloud_object=0`. No unresolved test orphan key remains. |
| Backend regression | PASS | Current full suite: **139 passed, 2 platform skips**. Focused Windows and WSL offline gate/storage checks: **29 passed** each. These are mock/local results, not live storage verification. |

## Execution and safeguards

The test was run once from `backend/` in WSL with the existing approved
credentials, using:

```bash
uv run --no-project --isolated --python 3.12.10 --with-requirements requirements.txt --with python-dotenv python -m scripts.run_live_storage_validation --private-verified
```

It created only two
disposable synthetic users and two predeclared random keys sharing a test
prefix: one successful upload and one forced metadata-write failure. It tests
API authorization, unsigned object GET denial, SHA-256 equality between
authorized API and S3 bytes, compensating cleanup, and exact-key absence. Its
`finally` block deleted only test-owned rows and keys; a failed cleanup would
have printed the exact test-specific keys requiring manual review. It then ran
aggregate, read-only orphan reconciliation. No migration, deployment,
production request, or ML access was part of this procedure. Neither `.env`
file was modified and no credential or connection string was printed.

Sydney PostgreSQL and Singapore storage cannot commit atomically. Timeout
ambiguity still requires orphan reconciliation and private bucket monitoring.
This testing run does not verify the production bucket, production credentials,
Render deployment or real-user traffic; those remain separate **NO-GO** gates.
