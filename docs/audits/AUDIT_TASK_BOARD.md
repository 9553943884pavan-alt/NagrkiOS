# NagrikOS audit task board

Baseline: `cdfa02a7d43e478da49b16a5e43dba070cc003cb` on `main`; working tree clean at start. Scope is local code and read-only hosted checks. Production deployment and data changes are excluded.

| Priority | Area | Owner | Status | Gate |
| --- | --- | --- | --- | --- |
| P0/P1 | Access control, authentication, CSRF, cross-user isolation | Lead + backend | Validated locally | Negative authorization tests and code review; hosted auth remains Blocked |
| P0/P1 | Data integrity, attachment ownership, transactions | Backend | Fixed and Validated locally | Isolated database/storage tests |
| P1/P2 | CI, deployment configuration, secrets and integrations | Infrastructure | Fixed and Validated locally | actionlint and read-only health checks; production deployment Blocked |
| P1/P2 | Frontend routes, state, accessibility, visual layout | Frontend + independent QA | Fixed and Validated on tested routes | TypeScript, Chromium and viewport checks; untested routes recorded |
| P1/P2 | Dependency advisories and performance | Lead + frontend | Fixed and Validated locally | npm/pip audits, build and bundle measurements |
| P1/P2 | Independent regression and integration review | Independent QA + lead | Validated locally | Backend suite, isolated Chromium checks, workflow lint |
| P3 | Final audit reports and release decision | Lead | Validated | Evidence ledger and explicit untested areas; production release Blocked |

Statuses: Pending, In Progress, Fixed, Validated, Blocked. A scanner result alone cannot close a finding.
