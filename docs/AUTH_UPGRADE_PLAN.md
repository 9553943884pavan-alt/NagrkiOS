# Authentication upgrade plan

1. Add an additive account migration, preserving all users, sessions, cases, notes and files. Mark legacy demo identities so public mode cannot authenticate them. Seed demo identities only when development demo mode is explicitly enabled.
2. Keep password verification and cookie sessions in the backend; add verified citizen registration, email delivery, single-use hashed verification/reset tokens, rate limits, and a staff invitation endpoint restricted to administrators.
3. Split password and second-factor authentication. Add short-lived bounded challenges, recovery codes, factor replacement and a dedicated setup wizard with QR and manual key.
4. Update both React and the no-install UI to use the same API contract, then run backend security tests, TypeScript, production build, npm audit and browser checks where available.
5. Document deployment prerequisites, remaining limitations and exact validation evidence. Production mode must reject missing HTTPS cookie, encryption key, and mail configuration.
