# Security findings

**Assessment date:** 21 November 2026. Defensive local tests only; no production authentication attempts or credential exposure. The original audit fixes were later published to `main` with the operator's authorization; follow-up tests and remaining gates are in `FINAL_REMEDIATION_REPORT.md`.

| Area | Evidence | Assessment |
| --- | --- | --- |
| Object authorization | `get_complaint` scopes citizen records by owner and officer records by department; attachment fetch checks the linked complaint or uploader. Negative cross-citizen and cross-department tests passed. | No confirmed bypass in tested paths |
| Session and CSRF | Opaque hashed session tokens, expiry/idle checks, `SameSite=Strict` cookies, CSRF header/cookie/hash check on state-changing API calls, origin check. Tests cover CSRF and revocation. | Controls present; hosted cookie behavior untested |
| MFA and account lifecycle | TOTP replay guard and recovery-code tests pass; public signup cannot assign staff roles; staff invitation requires admin and password reauthentication. | Local controls tested; production MFA state unverified |
| Upload and storage | Image signature and Pillow decode, pixel/size bounds, re-encoding, random object keys, metadata ownership, private object access checks. | Local/failure-injection tests pass; live bucket privacy and durability unverified |
| CI and secrets | The original three workflows are manual, use pinned official actions, restricted permissions and protected environments. No tracked `.env`, key, database or build artifacts found in the audited tree. A non-deploying CI workflow has been prepared in the follow-up. | Manual cleanup intent guard deployed; cloud rules unchanged |

## Confirmed repairs

- **F-01, P2:** Complaint photo claim is now a conditional, owner-bound update with `complaint_id IS NULL`. A conflicting claim returns 409 and transaction rollback prevents a stray complaint. See `backend/tests/test_security.py`.
- **F-05, P2:** The manually dispatched demo credential cleanup now requires an explicit phrase and validates it before installing dependencies or touching the database. The existing protected `neon-admin` environment remains mandatory.
- **F-07, P1:** Pillow 12.3.0 was within the affected range of multiple critical/high image-decoder advisories, and this app decodes uploaded images. The requirements now select Pillow 13.0.0 and accepted `Image.open` formats are restricted to PNG, JPEG and WEBP. The cryptography bound now selects 50.0.2. The local backend suite passes after both updates. Render reports the patched commit deployed, but the installed production package versions were not independently verified.

## Residual risks and limits

- GitHub API currently reports no protection or ruleset on `main`; Neon production-branch protection could not be rechecked. This is a **P1 release-control risk** for a public launch, pending a separately authorized cloud change.
- The production administrator's current MFA enrollment and hosted sign-in are **unverified** here. The bootstrap record alone proves account existence, not authentication success.
- Mailjet send-before-commit can produce a dead link or misleading notification if a later transaction commit fails. This is **P2**, and the current synchronous API cannot provide exactly-once delivery across provider and database boundaries.
- Follow-up isolated tests cover missing or cross-session CSRF, a malicious Origin, immediate role downgrade, and MFA enrollment revoking old sessions. The focused suite passed 25 tests; no bypass was reproduced in these paths. Another two tests cover one-attempt Mailjet timeout behavior.
- The private storage bucket policy, hosted cross-origin cookies, and production role isolation were not exercised. Do not infer their correctness from local tests.
- A network-enabled final `npm audit --audit-level=moderate --json` reported zero advisories across 141 installed frontend dependencies. `pip-audit` initially reported 60 findings across Pillow 12.3.0, cryptography 48.0.1 and the local pip installer 25.0.1. After updating the two application libraries and the local installer, it reported **no known vulnerabilities across 51 installed packages**. These scans describe the local environment, not deployed Render packages. The Pillow upgrade follows its [13.0.0 security release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html); the cryptography upgrade follows its [changelog](https://github.com/pyca/cryptography/blob/main/CHANGELOG.rst).

No confirmed P0 remains in the tested local paths. The P1 Pillow finding is fixed in code and its commit was deployed, but production dependency versions and hosted authentication remain unverified. The unresolved release-control and verification risks keep public launch at **NO-GO**.
