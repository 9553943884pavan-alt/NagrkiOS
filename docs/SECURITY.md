# Security and privacy — NagrikOS v4

**Local hackathon demonstration only. Do not deploy to the public Internet or store real grievance/identity data.** Default accounts are intentionally published with `demo123` until you change them. Do not use 0.0.0.0, tunneling, or public exposure.

## Implemented controls

- **Argon2id** passwords with random salts and automatic login-time migration from older scrypt/PBKDF2 hashes. Users can change their passwords in Settings, which revokes every session.
- Optional **TOTP authenticator-app MFA**, with password-authenticated enrollment, code confirmation, one-use time steps, and session revocation after enable/disable. The TOTP secret is Fernet-encrypted in SQLite; its encryption key is separately stored in `~/.nagrikos/totp.key` unless `NAGRIKOS_TOTP_KEY` or `NAGRIKOS_TOTP_KEY_FILE` is set. Protect/back up the key separately. Losing it while MFA is enabled will prevent code verification.
- **Opaque HttpOnly SameSite=Strict session cookies**, hashed token verifiers in SQLite, 12-hour absolute expiry, 30-minute idle expiry, logout revocation, and server-checked CSRF cookie/header pair.
- **Login attempt throttling** per IP and account (8 failed attempts within rolling 15 minutes). Too many failures may briefly lock out several demo users sharing one IP.
- **Server-side authorization**: citizens see only own cases and public notes; officers see/update their own department only; admins have global case/analytics/export access. Admin rerouting clears an invalid assignee; non-admin cannot route cross-department.
- **Upload protection**: 5-MB body cap, extension and signature checks, Pillow image validation and max dimensions, EXIF/GPS metadata removal by re-encoding, randomized private file paths, ownership-checked download, and one-use attachment references. No real image classification is performed.
- SQLite parameterized queries, foreign keys, private file permissions on POSIX, generic login errors, minimized officer listing, CSV formula escaping, restrictive CORS, no-store API responses, CSP for dependency-free frontend, anti-clickjacking and no-sniff headers.

## Explicit limitations

1. The SQLite **complaint contents are not encrypted at rest**. Windows NTFS account permissions and device security still matter; use encrypted storage and dedicated secrets management for real-world deployments.
2. Demo accounts/passwords are deliberately public and MFA is opt-in. There is no verified registration, email/phone ownership proof, account recovery or SSO; do not claim identity verification.
3. A logged-in administrator can destructively reset the sandbox to known demo credentials. Disable this endpoint outside demo mode.
4. Plain HTTP localhost needs `COOKIE_SECURE=false` (default). HTTPS production would require `COOKIE_SECURE=true`, reverse-proxy hardening and HSTS. Do not serve this project publicly without redesign.
5. No antivirus/malware scanner for uploads, centralized monitoring, dedicated audit store, encryption-at-rest for cases, privacy retention controls, phishing-resistant WebAuthn/passkeys, rate limits on every endpoint, or independent penetration test.
6. Browser voice may use a remote vendor speech service and does not guarantee local operation or Awadhi transcription.
7. ML outputs are mock heuristics; cannot support emergency triage or government decisions. Human review is essential.

For the complete implementation summary and independent recommendations, see `AUDIT_V4.md`, `VALIDATION_V4.md`, and `ML_SCOPE_V4.md`.
