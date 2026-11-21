# Mailjet sending restriction: remediation and deployment decision

**Historical decision (earlier on 21 November 2026): BLOCKED — PROVIDER ACTION REQUIRED.** This document records the earlier restricted-key investigation. The owner subsequently updated local Mailjet credentials and authorized one live send. The new key's test message was accepted and the owner confirmed it reached Gmail Spam; see [MAILJET_LIVE_VERIFICATION.md](MAILJET_LIVE_VERIFICATION.md). Public deployment is still **NO-GO** pending deployed end-to-end checks.

## Evidence and root cause

The existing [Mailjet deployment record](MAILJET_DEPLOYMENT.md) reports HTTP 200 from a read-only profile request, HTTP 200 from a lookup showing the exact configured sender as active, and an API-key management view reporting the key active. A single controlled Send API v3.1 request to that sender then returned **HTTP 401 / `mj-0001`**; no message was accepted. [Mailjet defines `mj-0001` as a suspended API key](https://dev.mailjet.com/docs/email-api/send-api-v31/send-api-errors). This is **high-confidence evidence of a provider-side sending restriction**. The recorded evidence does not identify the reason for the restriction or prove the present dashboard status. Only the account owner and Mailjet Support can establish those facts. We did not re-probe the restricted account.

The backend uses the documented [HTTPS Send API v3.1 endpoint and message format](https://dev.mailjet.com/docs/email-api/send-api-v31/send-basic-email), with the public API key as the HTTP Basic username and the private secret as the password, as specified by [Mailjet authentication guidance](https://dev.mailjet.com/docs/email-api/email-api-overview/authentication). Its one-recipient success check requires HTTP 200/201, one `Status: success` result, the intended recipient, and a positive numeric `MessageID`. API acceptance alone does not prove inbox delivery.

## Code findings and fixes

- Password recovery previously returned HTTP 503 for an existing account when Mailjet failed but HTTP 202 for an unknown address. It now returns the same generic HTTP 202 body for both, with wording that does not claim an email was sent. Every allowed address schedules the account lookup and delivery after the response, so Mailjet latency no longer distinguishes known accounts in the response path. An unsuccessful send rolls back the reset token. The task runs in the web process; a restart after the response can lose the attempt, and there is no durable recovery queue.
- Provider failures now have bounded internal categories: suspended key (`mj-0001`), invalid credentials (`mj-0015`), unauthorized sender (`send-0008`), other authentication/permission rejection, rate limit, provider unavailability, transport failure, invalid response, and other request rejection. The browser still receives only a generic delivery error where one is appropriate. Logs contain only the category, never provider text, secrets, recipient addresses, or links.
- Per-message `Status: error` and `Errors` are checked, including a nested status code; a success result with an `Errors` list is rejected. There are no automatic retries. After a timeout, Mailjet might have accepted the message before the response was lost. A user retry can create another message while the first link is invalid because its database transaction rolled back. Check message activity before any manual retry; duplicate prevention cannot be guaranteed after an ambiguous timeout.
- The `mail_outbox` table exists in the schema but has no runtime delivery worker or retry path. It is not evidence that failed or interrupted background messages will be resent automatically.

## Account owner checklist

The steps below require account access; none of these states was newly verified in this investigation.

1. Check dashboard banners, compliance notices, and account email for a suspension, verification request, or Test Mode. If Mailjet requests account verification, follow its stated process. [Mailjet says Test Mode limits sending to 10 per hour and upgrading alone does not remove it](https://documentation.mailjet.com/hc/en-us/articles/360042624754-Blocked-or-Limited-Account-Reasons-and-How-to-Restore-Full-Functionality).
2. Under **Account → API Keys**, inspect the affected key's current status and any key-specific Daily Send Limit, including a limit of zero. Record the exact status without sharing the key or secret. Review Mailjet's [key limit guidance](https://documentation.mailjet.com/hc/en-us/articles/43977536821147-Daily-Send-Limit-for-Mailjet-API-keys).
3. Under **Account Settings → Senders & Domains**, confirm the exact `MAIL_FROM` address remains active. If sending from a controlled domain, confirm domain verification and SPF/DKIM show OK. The prior sender lookup was active, but current console state needs confirmation. See [Mailjet Quick Start](https://documentation.mailjet.com/hc/en-us/articles/37251169295003--Quick-Start-with-Mailjet).
4. Check the actual account plan, daily and monthly sending allowance, contact limit, and usage. Do not assume this account is on the Free plan. Check billing notices and invoices if applicable.
5. If the reason is unclear or the restriction requires intervention, use dashboard **Need help? → Support center** to [contact Mailjet Support](https://documentation.mailjet.com/hc/en-us/articles/5460904032795-How-to-Contact-Mailjet-Support). Ask for the exact restriction reason and legitimate reactivation steps. Do not work around a suspension with another key, account, SMTP, or provider.

## Support ticket draft — owner to review and submit

**Subject:** NagrikOS transactional Send API returns 401 / mj-0001 — request restriction reason and reactivation steps

> Hello Mailjet Support,
>
> We are preparing NagrikOS, a civic grievance application, to send transactional messages for signup verification, password reset, staff invitations, and security or MFA-related notices. A controlled Send API v3.1 request to the configured sender returned HTTP 401 with `ErrorCode: mj-0001`. Our local diagnostic record shows HTTP 200 for a read-only profile request and sender lookup, with the sender active; API-key management also reported the key active. No message was accepted. We paused further sending and public deployment.
>
> Could you identify the exact account or API-key sending restriction and its reason, including whether account verification, Test Mode, a compliance hold, or a key-level limit is involved? Please specify the legitimate steps to restore sending and how to confirm restoration before public use.
>
> We can provide the attempt timestamp, sanitized response or error identifier if available, application URL, expected sending volume, recipient-source details, and dashboard screenshots through a secure support channel. We will not include API keys, secrets, verification links, or reset tokens in the ticket.

## Verification after restoration

1. First confirm in the dashboard or Support response that the affected key is allowed to send and the configured sender is active. Obtain separate, explicit approval for **one** real message to an address the owner controls.
2. Use the existing Mailjet HTTPS integration to send that single transactional message. Record only the timestamp, HTTP status, Mailjet `Status`, and non-sensitive message identifier. Do not print credentials, raw provider responses, or tokenized links.
3. Confirm accepted status in Mailjet message activity and actual receipt in the owned inbox. Acceptance without inbox receipt does not satisfy the deployment gate.
4. If the request times out or its outcome is uncertain, inspect Mailjet activity before deciding whether a retry is safe. Stop on a renewed `mj-0001` and return to Support.

## Tests and remaining gate

The historical remediation run used deterministic mocked Mailjet tests for success, suspended key, invalid credentials, unauthorized sender, per-message errors, rate limits, timeout/network failures, one-attempt behavior, token rollback, and identical recovery response status/body for known and unknown addresses. At that time the full backend run passed **198 tests with 3 skips**, and a later focused run passed **47 tests**. No live send was made during that earlier investigation. The owner subsequently authorized one real test with updated credentials; Mailjet accepted it and the owner confirmed receipt in Gmail Spam. See [the live verification record](MAILJET_LIVE_VERIFICATION.md) and [current release checklist](FINAL_DEPLOYMENT_CHECKLIST.md) for the updated gate. Public signup, recovery and broader deliverability remain unverified.
