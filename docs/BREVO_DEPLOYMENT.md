# Brevo transactional email deployment

NagrikOS sends verification, password reset, invitation, and security-notification emails through Brevo's [HTTPS transactional endpoint](https://developers.brevo.com/reference/send-transac-email). The backend sends plain-text content using `POST https://api.brevo.com/v3/smtp/email` with an `api-key` header. It treats only HTTP 201 plus a valid `messageId` as acceptance by Brevo. Acceptance is not proof of inbox delivery.

Set these backend environment variables in Render's secret settings or the Git-ignored `backend/.env` for local testing:

| Variable | Value |
| --- | --- |
| `BREVO_API_KEY` | Your Brevo API key; backend secret only |
| `MAIL_FROM` | Sender email approved in Brevo |
| `PUBLIC_BASE_URL` | HTTPS origin serving the account screens, such as your deployed app URL |
| `NAGRIKOS_MODE` | `public` for deployment |
| `COOKIE_SECURE` | `true` for deployment |
| `NAGRIKOS_TOTP_KEY` | Persistent Fernet key, unchanged across restarts |

The existing database, CORS, and other public-mode settings remain required. Copy variable names from [`.env.example`](../.env.example); do not commit actual values or put them in `VITE_` frontend variables. The runtime app does not load `.env` automatically; start Uvicorn with `--env-file .env` when testing locally from `backend`, or set environment variables in Render.

Approve the sender address or its domain in Brevo before live traffic. The [Brevo guide](https://developers.brevo.com/docs/send-a-transactional-email) documents the `sender`, `to`, `subject`, and `textContent` fields. No extra Python email SDK is required.

When Brevo rejects a request, times out, returns a non-201 status, or omits a valid `messageId`, the API returns a generic 503. Signup, reset-token issuance, and invitations then roll back. Account-facing responses never include keys or raw verification/reset links. Automated tests replace the network call with an in-memory stub; they do not send real mail. In demo mode without Brevo settings, sign-in and dashboards work, while signup and recovery transparently report unavailable.

Live sender approval, inbox delivery, bounce handling, and deployment network access still need validation in the deployed environment.
