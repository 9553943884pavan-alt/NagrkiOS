# Mailjet live delivery verification

**Date:** 21 November 2026 (Asia/Kolkata)  
**Decision:** **Mailjet single-message receipt confirmed; public deployment remains NO-GO pending end-to-end checks.** The newly configured key submitted one message to Mailjet. The owner later reported that it reached Gmail Spam and marked it “Not spam.”

## Preflight

| Check | Result | Evidence |
| --- | --- | --- |
| `backend/.env` Mailjet key, secret, and sender present and well formed | PASS | Loaded locally without printing values or authorization headers. |
| Neon connection target identified without connecting | PASS | `DATABASE_URL`/`DIRECT_URL` classify as Sydney production. No database request, write, migration, or user creation was made. |
| Mailjet read-only authentication | PASS | `GET /v3/REST/myprofile`: HTTP 200. |
| Configured sender active | PASS | `GET /v3/REST/sender/{sender}`: HTTP 200; exact configured address matched and status was `Active`. |
| Configured API key active | PASS | `GET /v3/REST/apikey`: HTTP 200; matching key reported active. |
| Sending permissions and limits | PARTIAL | The checked read-only endpoints did not expose a definitive send entitlement or daily limit. A live send was required to prove acceptance. Check the Mailjet dashboard for plan and key-specific limits if needed. |

## Single authorized send

- **Attempt count:** **1** POST to `https://api.mailjet.com/v3.1/send`; no automatic or manual retry.
- **Recipient:** the active `MAIL_FROM` address from `backend/.env` (value omitted here).
- **Subject:** `NagrikOS — Mailjet Delivery Test`
- **Body:** `This is an authorized transactional email delivery test for NagrikOS. No action is required.`
- **HTTP status:** **200**.
- **Sanitized Send API result:** one `Messages` item with `Status: success`, exact recipient match, and a positive `MessageID`.
- **Message ID:** `1152921546957251673`.
- **Classification:** **accepted by Mailjet**. No `mj-0001` restriction was returned for this attempt.

## Read-only delivery check

`GET /v3/REST/message/1152921546957251673` returned HTTP 200. Its immediate status was `queued`; a later read-only check showed `sent`. `GET /v3/REST/messagehistory/1152921546957251673` returned HTTP 200 with a `sent` event. No `delivered` status or event was observed in these checks.

**Delivery status:** **accepted and marked sent by Mailjet; owner-confirmed receipt in Gmail Spam.** The API checks did not show a `delivered` event, but the owner directly confirmed receipt and marked the message “Not spam.” [Mailjet distinguishes sent from delivered](https://documentation.mailjet.com/hc/en-us/articles/360043229453-Why-Are-My-Emails-Showing-as-Sent-and-Not-Delivered). Do not send another test message as part of this verification.

## Remaining gate

The new credentials authenticate, Mailjet accepted one message, and the owner confirmed receipt, so the earlier `401 / mj-0001` outcome was **not reproduced** with this configuration. This does not establish the old key's current status or explain its prior restriction. Gmail placed the message in Spam; public signup, recovery and broader deliverability remain unverified. Public deployment remains **NO-GO** until the other deployment gates and deployed browser tests pass. No Render or Vercel deployment was attempted.

The one-shot diagnostic is in `backend/scripts/mailjet_live_verification.py`. It uses the existing `app.account.send_mail` transport for the POST, blocks a second POST within the process, prints only bounded classifications, and does not open the application database. The script was syntax checked; no application code or configuration was changed for this verification.
