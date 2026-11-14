# NagrikOS architecture

This describes the implemented v4 grievance workflow with the v5 account lifecycle. React and the no-install browser UI call the same FastAPI routes. The browser does not decide which records a user may access; FastAPI enforces role and record scope before reading or changing data.

```mermaid
flowchart TB
  subgraph Browser["Browser clients"]
    React["React and TypeScript UI<br/>citizen, officer, administrator"]
    Lite["No-install JavaScript UI<br/>served by FastAPI"]
  end

  Vite["Vite development server<br/>same-origin /api proxy"]
  PublicHost["HTTPS reverse proxy and static React<br/>public deployment configuration"]

  subgraph Backend["FastAPI application"]
    Guard["Origin, CORS, CSRF<br/>and session-cookie checks"]
    Account["Account lifecycle<br/>signup, verification, recovery,<br/>MFA, staff invitations"]
    Scope["Server-side role and<br/>record-scope checks"]
    Cases["Grievances, notes,<br/>attachments, reports"]
    Heuristics["Deterministic mock AI<br/>classification, urgency, ETA"]
  end

  subgraph Persistence["Local persistence"]
    DB[(SQLite database)]
    Photos["Private photo files<br/>backend/uploads"]
    MFAKey["TOTP encryption key<br/>environment or local key file"]
  end

  SMTP["SMTP with STARTTLS<br/>public mode"]
  MailSink["Development mail sink<br/>SQLite, loopback only"]
  PasswordCheck["Pwned Passwords range API<br/>public password checks"]

  React --> Vite --> Guard
  React -.-> PublicHost -.-> Guard
  Lite --> Guard
  Guard --> Account
  Guard --> Scope --> Cases
  Cases --> Heuristics
  Cases --> DB
  Cases --> Photos
  Account --> DB
  Account --> MFAKey
  Account --> SMTP
  Account --> MailSink
  Account --> PasswordCheck
```

The Vite proxy is for local React development. The no-install UI is served at `/` with assets under `/lite/`. A public React deployment must serve the frontend and `/api` from the same HTTPS origin through deployment infrastructure. SMTP and the external password check apply in public mode; the local mail sink applies only in demo mode. No cloud database or storage service is part of this architecture.

## Trust and account flow

1. Public signup creates **citizen accounts only**. The server canonicalizes email, checks the password policy, and sends a short-lived verification link. Verification also requires the password chosen at signup. Repeating signup cannot replace pending credentials, and an active staff invitation reserves its email address.
2. Login verifies the password first. Accounts with TOTP then receive a short-lived, bounded second-factor challenge. FastAPI creates a session only after the TOTP or one-time recovery code succeeds.
3. Sessions are opaque, revocable HttpOnly cookies with a 12-hour absolute lifetime and 30-minute inactivity limit. SameSite is Strict; public mode requires Secure cookies and HTTPS. Authenticated state changes require the matching CSRF cookie and header. Expired cookies do not block public recovery, while protected routes still reject them.
4. Email verification, password reset, and staff invitations use random, expiring, single-use URL-fragment tokens stored only as hashes. Reset revokes sessions and outstanding challenges and tokens. Changing a password or disabling MFA revokes sessions; enabling MFA rotates the session.
5. Staff accounts are created through an administrator-authorized invitation after password reauthentication. The first public administrator is provisioned locally with `backend/scripts/provision_admin.py`. There is no public privileged-role signup or administrator MFA-reset shortcut.

Account logic lives in [account.py](../backend/app/account.py), [auth.py](../backend/app/auth.py), and [main.py](../backend/app/main.py). The React account screens are [Login.tsx](../frontend/src/pages/Login.tsx) and [Settings.tsx](../frontend/src/pages/Settings.tsx); [account-ui.js](../backend/static/account-ui.js) and [account-settings.js](../backend/static/account-settings.js) provide the no-install equivalents. [AUTH_SECURITY_V5.md](AUTH_SECURITY_V5.md) details security controls and deployment requirements.

## Role and record boundaries

| Capability | Citizen | Department officer | Administrator |
| --- | --- | --- | --- |
| Submit a grievance | Yes | No | Yes |
| List and read grievances | Own submissions | Own department | All |
| Change priority or status; add notes | No | Own department | All |
| Route to another department | No | No | Yes |
| Assign an officer | No | Officer in the case's department | Officer in the case's department |
| Dashboard | Own submissions | Department desk | Global overview |
| Insights, department analytics, CSV export | No | No | Yes |
| Invite staff | No | No | Yes, after reauthentication |
| Reset synthetic data | No | No | Demo mode only |

The backend applies citizen ownership and officer department filters in SQL queries and individual-record checks. Similar-case results, attachment access, notes, officer lists, and reports also respect these boundaries. Frontend routes mirror the permissions for navigation; they are not the authorization boundary.

## Persistence and services

| Component | Responsibility |
| --- | --- |
| `users`, `sessions`, `login_attempts` | Verified identities and roles, password and encrypted MFA state, revocable sessions, throttling |
| `account_tokens`, `auth_challenges`, `recovery_codes`, `staff_invitations` | Hashed verification/reset tokens, bounded MFA challenges, hashed one-time codes, authorized staff provisioning |
| `complaints`, `history`, `notes`, `attachments` | Grievance records, activity, follow-ups, and photo ownership metadata |
| `backend/uploads` | Private photo bytes; access goes through FastAPI ownership and case-scope checks |
| `mail_outbox` | Local development mail sink; unavailable in public mode |
| `backend/app/ai.py` | Deterministic heuristic outputs for classification, urgency, ETA, and illustrative image hints; no production ML model |

SQLite migrations in [db.py](../backend/app/db.py) are additive. [migrate_auth_v5.py](../backend/scripts/migrate_auth_v5.py) makes a backup before applying them and checks database integrity. Existing users, cases, notes, files, history, and compatible sessions are preserved; credential and MFA changes revoke affected sessions. A later PostgreSQL or cloud-storage migration would be separate work.

## API surface

| Route group | Access and purpose |
| --- | --- |
| `/api/auth/config`, `/api/auth/signup`, `/api/auth/verify-email` | Public account entry; demo credentials appear only for loopback demo clients |
| `/api/auth/login`, `/api/auth/mfa/challenge`, `/api/auth/accept-invitation` | Password-first sign-in, second-factor completion, invitation acceptance |
| `/api/auth/forgot-password`, `/api/auth/reset-password` | Generic recovery request and token-based reset |
| `/api/auth/me`, `/api/auth/logout`, `/api/auth/security`, `/api/auth/password` | Current session and account security |
| `/api/auth/mfa/setup`, `/api/auth/mfa/enable`, `/api/auth/mfa/cancel`, `/api/auth/mfa/disable` | Authenticator enrollment, confirmation, cancellation, and removal |
| `/api/auth/staff-invitations` | Administrator only, with current-password reauthentication |
| `/api/auth/dev-mailbox` | Loopback demo mode only |
| `/api/complaints`, `/api/complaints/{id}`, `/api/complaints/{id}/notes` | Role-scoped grievance workflow |
| `/api/attachments`, `/api/attachments/{filename}` | Private photo upload and authorized retrieval |
| `/api/citizen/overview`, `/api/officer/overview` | Citizen and department dashboards |
| `/api/users/officers` | Officer directory; department-scoped for officers |
| `/api/dashboard`, `/api/insights`, `/api/departments`, `/api/export/complaints.csv` | Administrator reporting |
| `/api/ai/analyze` | Authenticated heuristic preview; similar cases filtered by role |
| `/api/health`, `/api/meta` | Public health and UI metadata |
| `/api/admin/reset-demo` | Demo administrator only; destructive and revokes sessions |

## Runtime modes

| | Local demo | Public configuration |
| --- | --- | --- |
| Accounts | Seeds synthetic identities only for an empty database | No seeded accounts or demo credential exposure |
| Email | Local SQLite sink, readable only from loopback | Configured SMTP delivery with STARTTLS |
| Password screening | Local common-password blocklist | Blocklist plus breached-password range check |
| Cookies and transport | Local HTTP development settings | Secure cookies, HTTPS public URL, explicit origins, persistent TOTP key |
| API documentation | Local development access | Disabled |

`NAGRIKOS_MODE` must be set explicitly. Public startup rejects missing required configuration. These checks do not establish that any particular public hosting setup has been reviewed or deployed.
