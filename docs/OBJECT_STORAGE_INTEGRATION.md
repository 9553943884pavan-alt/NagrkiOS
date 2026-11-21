# Private Neon Singapore attachment storage

The existing PostgreSQL database stays in the Sydney project `winter-meadow-40329605` (`aws-ap-southeast-2`). Its `DATABASE_URL`, `DIRECT_URL`, Alembic revision and migration workflow are unchanged. The owner identified a **separate** Singapore project, `cold-violet-69814991`, for private Neon Object Storage. The Sydney project reports `region_unavailable` for Object Storage; do not try to enable it there. The Singapore project is not a database migration target.

Neon documents [S3-compatible branch endpoints and `AWS_*` credentials](https://neon.com/blog/building-a-private-searchable-photo-library-on-the-neon-backend), including path-style `<endpoint>/<bucket>/<key>` access. [Bucket visibility is set in Neon](https://neon.com/blog/building-neon-object-storage), not by application S3 ACL or bucket-policy calls. The app uses backend-only boto3 SigV4 requests. The production bucket and branch-scoped credentials passed a read-only check; production object writes and authorized reads remain untested.

## Separate environment targets

| Purpose | Sydney PostgreSQL connection | Singapore Object Storage branch | Storage endpoint | Bucket |
| --- | --- | --- | --- | --- |
| Testing | Existing **testing** pooled `DATABASE_URL`; direct `DIRECT_URL` only for protected schema work | `br-lively-base-azf2mt0j` | `https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech` | `nagrikos-attachments`, private (owner reported) |
| Production | Existing **production** pooled `DATABASE_URL`; no database move | `br-divine-grass-azierqs7` | `https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech` | `nagrikos-attachments`, private; read-only bucket check passed |

Both storage branches use `AWS_REGION=ap-southeast-1`. The adapter pins each storage endpoint to its matching Sydney pooled database host. It rejects an unknown branch, a production endpoint with a testing database, and a testing endpoint with a production database. These are separate Neon projects: branching or resetting one does not transactionally roll back the other.

## Isolated testing example

The following values are for a separately isolated **testing** process, paired with a Sydney **testing** `DATABASE_URL`. Do not apply them to the current production `backend/.env` or Render. `DIRECT_URL` is only for approved schema work. Do **not** run `neon env pull` into `backend/.env`; it could replace Sydney URLs with Singapore project URLs. For testing storage, use these backend-only entries with the two credential values from the **testing storage branch** in Neon Console:

```dotenv
OBJECT_STORAGE_BACKEND=neon
OBJECT_STORAGE_BUCKET=nagrikos-attachments
AWS_ENDPOINT_URL_S3=https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=<testing-storage-access-key-id>
AWS_SECRET_ACCESS_KEY=<testing-storage-secret-access-key>
NAGRIKOS_REQUIRE_DURABLE_STORAGE=true
```

Leave `OBJECT_STORAGE_ENDPOINT_URL`, `OBJECT_STORAGE_REGION`, `OBJECT_STORAGE_ACCESS_KEY_ID`, and `OBJECT_STORAGE_SECRET_ACCESS_KEY` blank or remove them in Neon mode. With a Sydney PostgreSQL URL, the existing application configuration also requires `NAGRIKOS_MODE=public`, HTTPS `PUBLIC_BASE_URL`, `COOKIE_SECURE=true`, valid mail settings and a persistent TOTP key; follow the main backend setup guide for those entries. Never put credentials in `.env.example`, Vercel, React code, GitHub workflow inputs, logs or API responses. The app does not auto-load `.env`; load `backend/.env` into the backend process environment using the existing local-start method.

For production, use the already provisioned production storage branch's own credential pair and endpoint `https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech`. Keep production Sydney `DATABASE_URL` paired with production storage and set the same backend, bucket, region and durable-storage flag in Render secrets. Do not reuse testing storage credentials in production. `DIRECT_URL` is for schema migration, not the Render runtime. The production bucket passed a read-only private-access check, but a production object round trip and restart persistence are not yet verified.

When `OBJECT_STORAGE_BACKEND` is unset or `s3`, the existing generic `OBJECT_STORAGE_*` S3 configuration remains available for older deployments. Neon mode requires the `AWS_*` variables above and rejects mixed credential sets. Public startup fails closed when durable storage is required but not configured; photo upload fails closed without durable storage.

## Manual testing and production checklist

1. In Neon Console, select Singapore project `cold-violet-69814991` and the intended storage branch. Confirm its branch ID, endpoint and bucket access is **private**. For production, recheck the existing bucket and scoped credentials before deployment.
2. Keep the Sydney pooled `DATABASE_URL` for the matching testing or production branch. Verify the DB/storage pair before starting the backend. Leave `DIRECT_URL` and database workflows untouched.
3. Add the backend-only values above locally or as Render environment secrets. Do not expose any `AWS_*` value to Vercel. Restart only the intended environment after review.
4. With explicit approval for live writes, exercise a synthetic photo round trip through the authenticated FastAPI attachment route. Check anonymous and wrong-user denial, officer department scope, private bucket access, restart persistence, and failure cleanup. Do not test against production first.
5. Review orphan/missing counts with the read-only reconciliation script before considering any deletion. Keep original local files until object copy, hashes and metadata have been verified.

The adapter enforces HTTPS, SigV4 and path-style addressing and validates the configured branch, region and bucket. The production read-only check covered existing private access and credential scope; it does **not** prove live write/read behavior or restart persistence.

## Application behavior and existing attachments

`/api/attachments` keeps its response contract. FastAPI checks file extension, magic bytes, decoded image, dimensions and size, re-encodes to strip metadata, and writes under a random 24-hex-character key. The `attachments.filename` primary key is the object key; ownership and complaint links remain in Sydney PostgreSQL. A failed put creates no metadata row. A failed metadata insert requests idempotent object deletion. An uncertain cleanup can leave an orphan for operator review. The database and storage projects cannot commit atomically, so compensating deletion and reconciliation are required.

Downloads check the metadata row and citizen/department/admin case scope **before** fetching bytes. Unattached uploads remain uploader-private. FastAPI serves authorized responses; bucket URLs and object listings are never exposed to browsers. The [read-only reconciliation script](../backend/scripts/audit_attachment_storage.py) prints aggregate orphan/missing counts only. It does not delete objects.

Existing files in `backend/uploads/` are retained and remain a read-only legacy fallback. PostgreSQL data migration moves attachment **metadata**, not bytes. Back up local files and plan a separate no-overwrite copy to the approved private bucket, then compare keys and hashes before deleting any original. On Render Free, local files are ephemeral, so do not cut over with unresolved legacy bytes.

## Verification status

On 2026-11-21, `python -m pytest tests -q` in `backend/` passed **139 tests** with two platform skips. The focused offline storage and live-harness gate checks passed **29 tests**. `npm.cmd run typecheck` and `npm.cmd run build` in `frontend/` both passed; no frontend source was changed. The approved Singapore **testing** bucket completed one synthetic live upload, private-access check, failure-recovery check and cleanup; see [the exact validation record](NEON_LIVE_STORAGE_VALIDATION.md). The production bucket and credentials later passed read-only checks; no production object write or Render restart has been verified. No real attachment data or ML dataset was uploaded.
