# NagrikOS deployment readiness — 21 November 2026

**Decision: NOT READY for public traffic.** The repository is prepared for a controlled Render/Vercel deployment review, but neither service was deployed in this task. Use the [final deployment checklist](FINAL_DEPLOYMENT_CHECKLIST.md) for exact settings and acceptance gates.

| Component | Verified preparation | Remaining gate |
| --- | --- | --- |
| Sydney PostgreSQL | Production branch `br-super-glitter-a769u0u1` migrated to Alembic `20261114_01`; 12 application tables verified, no initial users or complaints; READY pre-migration backup `br-square-sunset-a7thmw2g` retained. | Review branch protection (previously reported disabled), configure the pooled TLS URL in Render, bootstrap one guarded real admin, run deployed auth/CRUD tests. Do not rerun initial migration. |
| Singapore private storage | Production branch `br-divine-grass-azierqs7`, private `nagrikos-attachments` bucket and branch credentials passed read-only verification; testing branch passed a synthetic live round trip. | Production attachment write, authorized download, denial and restart persistence remain untested and require separate approval. |
| Mailjet | New credentials authenticated; one authorized Send API v3.1 test returned success and the owner confirmed receipt in Gmail Spam, then marked it “Not spam.” | Public signup, recovery and wider deliverability remain untested. See [live verification](MAILJET_LIVE_VERIFICATION.md). |
| Backend | Render Blueprint now pins Singapore, Python 3.12.11, health path, secure public settings, production-only storage and manual deploy trigger. Startup checks Alembic head and does not migrate. | Configure actual Render secrets and final Vercel HTTPS origin; verify hosted startup, persistence, storage and monitoring. Health alone is not a dependency probe. |
| Frontend | Vercel programmatic rewrites use same-origin `/api`, no API cache and SPA fallback. Typecheck and build passed; production demo identity picker is removed. | Configure Render origin in Vercel and test actual HTTPS proxy, cookies, CSRF, deep links and browser flows. |
| Release safety | Initial production migration workflow excluded; manual admin write workflows pin the Sydney production target before any write. `.env` remains ignored. | Confirm protected GitHub environment secrets and reviewers before any owner-approved manual admin workflow. |

[Render warns that Free web services are unsuitable for production applications](https://render.com/docs/free): instances can sleep, restart and lose local state. NagrikOS uses durable PostgreSQL and private storage, but in-process password-recovery background tasks can still be lost on restart. Accept or replace this availability risk before public traffic.

No cloud deployment, production SQL write, production storage write, real email send, or Track A ML change was performed in this readiness review.
