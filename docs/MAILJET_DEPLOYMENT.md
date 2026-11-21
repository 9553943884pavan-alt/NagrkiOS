# Mailjet transactional email deployment

NagrikOS sends signup verification, password reset, staff invitation, and security-notification emails through Mailjet's [HTTPS Send API v3.1](https://dev.mailjet.com/docs/email-api/send-api-v31/send-basic-email). This is an HTTPS request on port 443, not an SMTP connection. The backend uses [HTTP Basic authentication](https://dev.mailjet.com/docs/email-api/email-api-overview/authentication): the public API key is the username and the private API secret is the password. Neither value is sent to the frontend.

## Mailjet account setup

1. Create a Mailjet account on the Free plan. [Mailjet currently lists](https://www.mailjet.com/pricing/) 6,000 emails per month and 200 per day, with no credit card required at signup. The daily limit can delay short-lived verification links if it is exceeded.
2. In Mailjet, open **Account Settings > Senders & Domains**, add the address you will use for `MAIL_FROM`, click its confirmation link, and confirm the sender is **Active**. An owned sending domain with SPF and DKIM is preferable for public delivery. See Mailjet's [sender guide](https://documentation.mailjet.com/hc/en-us/articles/360042759253-How-to-add-a-sender-address) and [domain guide](https://dev.mailjet.com/docs/email-api/getting-started/verify-your-domain).
3. Open **Account Settings > API Keys** and securely copy the public API key and private secret for the same Mailjet account. Store them in the Git-ignored `backend/.env` for local testing and in Render's backend secret settings for deployment. Do not place them in Git, Vercel, `VITE_` variables, command-line arguments, or screenshots.

| Backend variable | Value |
| --- | --- |
| `MAILJET_API_KEY` | Mailjet public API key |
| `MAILJET_SECRET_KEY` | Mailjet private API secret |
| `MAIL_FROM` | The exact active sender email validated in Mailjet |
| `PUBLIC_BASE_URL` | HTTPS origin of the Vercel account screens in public mode |

The app does not auto-load `backend/.env`. For local testing, start Uvicorn from `backend` with `--env-file .env`, or load the values into the process environment. Render's Blueprint prompts for the three Mailjet settings. Public startup refuses missing email settings. In demo mode without Mailjet settings, login and dashboards work, while signup and recovery transparently report unavailable.

## Acceptance and failure behavior

For each email, the backend sends one `Messages` item with one recipient and a plain-text body. It treats a request as accepted only when Mailjet returns HTTP 200 or 201 with a single result whose `Status` is `success`, whose recipient matches the intended address, and whose `MessageID` is a positive integer. [Mailjet documents these response fields](https://dev.mailjet.com/docs/email-api/send-api-v31/send-basic-email). Acceptance is not proof that the message reached an inbox; check Mailjet's message activity and the recipient inbox separately.

Rejected credentials, inactive senders, rate limits, timeouts, network failures, and malformed or unsuccessful responses fail closed. Signup, password-reset token issuance, and invitations then roll back. Signup and invitations receive a generic 503. Password-recovery requests return the same generic 202 response for known and unknown addresses; lookup and delivery run after the response, and no reset token commits if delivery fails. This in-process background attempt is not a durable queue and can be lost on worker restart. The backend logs only a bounded provider-failure category. Raw API errors, keys, verification links, and reset tokens are not returned to the browser or logged. Automated tests stub the provider and never send real email.

Before public signup traffic, test a single message to an address you own, confirm acceptance in Mailjet, and confirm inbox delivery separately. Then exercise signup verification, password reset, staff invitation, and security notification through the deployed `/api` proxy.

## Live checks

**Updated credentials, 21 November 2026:** One authorized Send API v3.1 test was accepted (HTTP 200, `Status: success`). Mailjet message activity later showed `sent`; the owner confirmed receipt in Gmail Spam and marked it “Not spam.” See [MAILJET_LIVE_VERIFICATION.md](MAILJET_LIVE_VERIFICATION.md).

**Earlier restricted-key result:**

The earlier configured credentials authenticated successfully against Mailjet's read-only profile endpoint (HTTP 200), and the exact `MAIL_FROM` address appeared as an active sender (HTTP 200). A controlled Send API test addressed only to that verified sender failed with HTTP 401 and Mailjet error `mj-0001`. [Mailjet defines `mj-0001` as a suspended API key](https://dev.mailjet.com/docs/email-api/send-api-v31/send-api-errors). API-key management reported the key as active at that time; [Mailjet's account-block guide](https://documentation.mailjet.com/hc/en-us/articles/360042624754-Blocked-or-Limited-Account-Reasons-and-How-to-Restore-Full-Functionality) directs unresolved cases to [support](https://documentation.mailjet.com/hc/en-us/articles/5460904032795-How-to-Contact-Mailjet-Support). No message was accepted on that earlier attempt. The updated credentials' successful test is recorded above; public signup and password recovery still require deployed end-to-end verification.

See [MAILJET_REMEDIATION.md](MAILJET_REMEDIATION.md) for the owner checklist, support ticket draft, and current deployment decision.
