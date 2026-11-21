# Release readiness

**Decision, 21 November 2026 (Asia/Kolkata): NO-GO for a production redeploy or public launch.** The audit repairs are committed locally as `c0366c7e781a93fb07b66821b8ab6ec85564c53d` and have not been pushed or deployed. The existing hosted services answered health checks, but that does not prove the hosted application uses the patched Python libraries or that user journeys work end to end.

## Gate assessment

| Gate | Status | Evidence / next step |
| --- | --- | --- |
| No unresolved P0/P1 in local code | PASS locally | P1 Pillow decoder advisories addressed by Pillow 13.0.0, accepted-format restriction and passing local tests; production still needs an approved release |
| Existing and new tests pass | PASS locally | Backend 220 passed, 2 skipped; frontend typecheck/build; browser smoke on tested routes |
| No unauthorized access or secret exposure | PASS in tested paths | Negative local authorization and CSRF tests; no tracked `.env`/key/database artifact found; hosted auth untested |
| Desktop/mobile layouts | PARTIAL | Login and selected citizen/officer views checked; all routes/modals/zoom/long text and Firefox/WebKit not covered |
| No known destructive production behavior | PARTIAL | No production writes were made; manual demo credential cleanup now has an intent guard, but changes are local |
| Dependency advisories | PASS locally, production unverified | npm audit 0; pip-audit 0/51 after patched upgrades; deployed Python versions unknown |
| Production authentication and MFA | BLOCKED | Existing admin account was created previously; current sign-in, MFA enrollment and recovery were not tested during this audit |
| Production controls and integrations | BLOCKED | Prior review found unprotected GitHub `main` and Neon production branch; Mailjet/account mail, durable object storage and live writes not verified here |

## Required before an approved production release

1. Review the local audit commit and six reports, then authorize a separate push/deployment with a rollback plan. A push may trigger hosting automation, so it was intentionally withheld under the audit brief's no-deploy boundary.
2. Verify production resolves Pillow 13.0.0 or later within the approved 13.x range and cryptography 50.0.2 or later within 50.x; rerun backend tests and vulnerability scans in the release build.
3. Verify the protected administrator's interactive login and MFA enrollment without exposing credentials or recovery codes; verify citizen, officer and admin flows in a safe staging environment before public traffic.
4. Review GitHub `main` and Neon production branch protection, and verify private storage bucket policy and hosted cookie/CSRF behavior.
5. Resolve or explicitly accept the Mailjet send-before-commit consistency risk. The protected demo credential cleanup workflow also needs its missing `DIRECT_URL` configuration before it could run; do not dispatch it merely for this audit.

For a **private hackathon showcase**, the repaired local demo paths have passed the checks listed in `REGRESSION_TEST_RESULTS.md`. That is a narrower statement than a public production release decision. The existing hosted endpoints responded 200, but the hosted UI and deployed dependency versions were not revalidated after these local repairs.
