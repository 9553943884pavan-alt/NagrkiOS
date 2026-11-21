# Backend, database and storage review

**Date:** 21 November 2026. The API route inventory in `backend/app/main.py` and `backend/app/account.py`, database adapter and schema, object storage adapter, migrations and associated tests were reviewed. All write tests used isolated SQLite demo fixtures; production PostgreSQL and object storage were not modified.

## Confirmed repairs

| ID | Severity | Reproduction and cause | Repair | Validation |
| --- | --- | --- | --- | --- |
| F-01 | P2 | Complaint creation read an unclaimed attachment, then used an unconditional update; another request could claim it between those steps. | Owner-bound `UPDATE ... WHERE complaint_id IS NULL RETURNING` makes claim atomic; 409 causes transaction rollback. | Forced intervening claim test; backend 220 passed, 2 skipped |
| F-02 | P2 | Demo reset deleted user rows before their pending staff invitations, violating the invitation's inviter foreign key. | Delete pending invitation rows first, inside the existing demo-only transaction. | Reset-with-invitation regression; backend 220 passed, 2 skipped |
| F-07 | P1 | Pillow 12.3.0 decoded untrusted uploads despite critical/high advisories fixed only in 13.0.0. Cryptography 48.0.1 also had advisories and an upper bound below patched versions. | Require Pillow 13 and cryptography 50; restrict Pillow decoding to accepted PNG/JPEG/WEBP formats. | Updated local venv: 220 passed, 2 skipped; `pip-audit` 0 findings across 51 installed packages |

The SQL adapter binds user values as parameters. Its `?` to `%s` SQL-text replacement is simplistic but no current static query demonstrated user-controlled SQL interpolation or injection. The attachment claim relies on PostgreSQL and SQLite `RETURNING`, both already used elsewhere in the application.

## Controls reviewed

- Authentication dependencies gate role-specific routes. Complaint reads scope citizens to their submissions and officers to their department. Attachment reads enforce linked complaint access or unclaimed uploader ownership.
- Complaint creation, history and attachment claim run in a transaction with rollback on exception. Migration and production-target tests exist, and public startup guards require approved target settings.
- Image upload checks extension, signature, decoding, pixel count and processed size, then re-encodes before private storage. Random keys are validated; object reads are authorized through database metadata.
- Local negative tests cover cross-user/cross-department access, CSRF, MFA replay, and staff invitation role checks. This does not establish production configuration correctness.

## Remaining risks and untested paths

- **P2 delivery consistency:** `send_mail` is called before commit in several account flows. A provider-accepted email can outlive a failed database transaction. A durable outbox and idempotent worker would require a separate design and migration; no speculative rewrite was made.
- Production PostgreSQL transaction contention, index plans, connection-pool behavior, rollback after provider acceptance, and storage bucket policy were not load-tested here.
- Local storage failure injection exists in backend tests, but no live Neon bucket write/read or orphan reconciliation was run during this audit.
- Existing schema revision and production user data were not queried or altered in this audit. The earlier administrator bootstrap record is historical evidence only.
- The patched dependency versions were installed and tested locally. The deployed Render versions were not read or changed; a separately approved deployment is required to address production exposure.

References: [PostgreSQL `UPDATE`](https://www.postgresql.org/docs/current/sql-update.html), [SQLite `RETURNING`](https://www.sqlite.org/lang_returning.html), [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/core/connections.html#using-transactions), [OWASP API BOLA](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/).
