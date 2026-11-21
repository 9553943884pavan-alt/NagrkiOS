# NagrikOS deployment readiness — 21 November 2026

**Historical readiness review; updated after the administrator bootstrap. Decision: NOT READY for public traffic.** Render and Vercel health endpoints now return HTTP 200 and the first administrator exists, but hosted auth and storage acceptance checks remain. Use the [final deployment checklist](FINAL_DEPLOYMENT_CHECKLIST.md) and [bootstrap record](ADMIN_BOOTSTRAP_COMPLETION.md) for current status.

| Component | Verified preparation | Remaining gate |
| --- | --- | --- |
| Sydney PostgreSQL | Production branch `br-super-glitter-a769u0u1` remains at Alembic `20261114_01`; one verified non-demo administrator, zero other users or complaints; READY post-migration backup `br-rapid-dew-a7tugwfo` retained. | Review branch protection (observed disabled), verify deployed auth/CRUD and MFA. Do not rerun initial migration. |
| Singapore private storage | Production branch `br-divine-grass-azierqs7`, private `nagrikos-attachments` bucket and branch credentials passed read-only verification; testing branch passed a synthetic live round trip. | Production attachment write, authorized download, denial and restart persistence remain untested and require separate approval. |
| Mailjet | New credentials authenticated; one authorized Send API v3.1 test returned success and the owner confirmed receipt in Gmail Spam, then marked it “Not spam.” | Public signup, recovery and wider deliverability remain untested. See [live verification](MAILJET_LIVE_VERIFICATION.md). |
| Backend | Render Blueprint now pins Singapore, Python 3.12.11, health path, secure public settings, production-only storage and manual deploy trigger. Startup checks Alembic head and does not migrate. | Configure actual Render secrets and final Vercel HTTPS origin; verify hosted startup, persistence, storage and monitoring. Health alone is not a dependency probe. |
| Frontend | Vercel programmatic rewrites use same-origin `/api`, no API cache and SPA fallback. Typecheck and build passed; production demo identity picker is removed. | Configure Render origin in Vercel and test actual HTTPS proxy, cookies, CSRF, deep links and browser flows. |
| Release safety | The first administrator was created through protected run `44916274619`; its one-time workflow was disabled and deleted, and its three bootstrap secrets removed. `.env` remains ignored. | Preserve `neon-admin` reviewers and `DATABASE_URL` for the separate demo cleanup workflow; review repository and Neon branch protection. |

[Render warns that Free web services are unsuitable for production applications](https://render.com/docs/free): instances can sleep, restart and lose local state. NagrikOS uses durable PostgreSQL and private storage, but in-process password-recovery background tasks can still be lost on restart. Accept or replace this availability risk before public traffic.

The original readiness review performed no cloud deployment or production SQL write. The later protected administrator bootstrap is recorded separately in [its completion report](ADMIN_BOOTSTRAP_COMPLETION.md).
