# Production administrator bootstrap completion

**Status, 21 November 2026 (Asia/Kolkata): completed and retired.** The first real administrator was created through the protected `neon-admin` GitHub environment. No username, email, password, hash, token or connection string is recorded here.

## Verified result

| Check | Result |
| --- | --- |
| Target | Neon project `winter-meadow-40329605`, production branch `br-super-glitter-a769u0u1`, Sydney; post-migration backup `br-rapid-dew-a7tugwfo` READY with production parent |
| Workflow | [Provisioning run 44916274619](https://github.com/9553943884pavan-alt/NagrkiOS/actions/runs/44916274619), `mode=provision`, head `b7b97204af61c9e32cc40005dd236dabc0b23ce3`, attempt 1, completed successfully after the required environment review |
| Before | Read-only production query: Alembic `20261114_01`, zero users, zero legitimate administrators, zero complaints |
| After | Read-only production query: Alembic `20261114_01`, one user, exactly one non-demo `admin`, verified email state, zero other users and zero complaints |
| One-time cleanup | Provisioning workflow disabled in GitHub, then deleted from `main`; `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_NAME`, and `BOOTSTRAP_ADMIN_PASSWORD` deleted from `neon-admin` |
| Retained | `neon-admin` environment, its `main` restriction and reviewer rule, and `DATABASE_URL`; the protected demo credential cleanup workflow still uses that URL |

The earlier [production attempt 44914568889](https://github.com/9553943884pavan-alt/NagrkiOS/actions/runs/44914568889) failed before an administrator was created. Read-only preflight [44915417558](https://github.com/9553943884pavan-alt/NagrkiOS/actions/runs/44915417558) later passed all validation stages and explicitly inserted no user. The successful production attempt above is the sole observed administrator creation. No Neon branch was restored, reset, migrated or deleted during this bootstrap.

## Ongoing administrator management

The one-time workflow is retired and must not be recreated for routine staff management. The existing administrator should sign in through the Vercel origin, enroll MFA, retain recovery codes securely, sign out and sign back in to verify MFA. Later staff access uses the application administrator-authorized invitation flow after password reauthentication; there is no public administrator signup. Treat loss of the sole administrator or MFA recovery as a separately reviewed recovery operation, not a reason to re-enable the bootstrap workflow.

## Remaining release checks

The database result proves account creation and role, not successful interactive login or MFA enrollment. Render and Vercel `/api/health` returned HTTP 200, but hosted signup, recovery, cookies/CSRF, role authorization, production object storage writes and durable attachment retrieval remain unverified. The production Neon branch and repository `main` were observed without branch protection; review those controls before public traffic. Keep the post-migration backup and all unrelated workflows.
