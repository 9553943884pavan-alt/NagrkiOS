# Neon, storage and Mailjet integration tasks — 21 November 2026

Use the [final deployment checklist](FINAL_DEPLOYMENT_CHECKLIST.md) for the release sequence and owner actions.

## Completed

- [x] Sydney testing and production schemas are at Alembic `20261114_01`; production has a READY pre-migration backup. Do not rerun the initial migration.
- [x] Backend runtime requires a pooled TLS production URL and checks Alembic head without startup DDL or demo seeding.
- [x] Singapore Neon Object Storage testing branch passed a synthetic live upload, authorized read, private denial, failure cleanup and reconciliation. Production bucket and credentials passed read-only verification.
- [x] Private S3 adapter uses HTTPS, SigV4, path-style addressing and branch pairing; public uploads fail closed without durable storage.
- [x] Updated Mailjet credentials authenticated and one authorized message was accepted and reached the owner's Gmail Spam folder. The owner marked it “Not spam.”
- [x] Offline backend tests, frontend typecheck/build, dependency audit and synthetic public startup passed in the final release review.

## Remaining before public traffic

- [ ] Review Neon production and backup branch protection, previously reported disabled; preserve the backup.
- [ ] Configure and verify actual Render/Vercel production settings and secrets after owner authorization. No cloud deployment was done here.
- [ ] Provision one real administrator through the protected, production-pinned manual workflow; enroll MFA. If demo accounts are later imported, disable their credential material through the guarded workflow.
- [ ] With separate approval, verify a production attachment write, scoped download, private direct access denial and restart persistence. Reconcile any orphans; do not delete production objects automatically.
- [ ] Run deployed browser signup, email verification, password recovery, MFA, role-scope, case, cookie, CSRF, API-cache and SPA-route checks. The one Mailjet test does not establish broader deliverability.
- [ ] If legacy SQLite data or local attachment bytes are imported later, plan an approved copy with counts, hashes and a rollback point. Preserve originals until verified.
