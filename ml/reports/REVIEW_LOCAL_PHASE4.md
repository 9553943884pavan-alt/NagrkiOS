# Phase 4 offline review workflow

This workflow is for the **30 hashed IDs** in the local OpenCity/Janaagraha Phase 3 queue. It reads redacted text from Git-ignored `ml/data/` and never contacts a network service. It does not approve any record by itself. The other 970 candidate narratives remain uncleared. As of implementation, no real review database, reviewer decisions or adjudications have been created.

## Before opening a real case

The project owner must approve the reviewer roster, access method and retention/deletion schedule. The local coordinator should confirm that the Phase 4 hardened processed file and regenerated queue are final, that their checksums agree with the source manifest, and that the local Windows account is authorized to read the restricted files. The review database binds to the SHA-256 of both files at initialization and refuses later changes. Reinitialize only through a documented new review round; the command refuses to replace an existing database.

Use a trusted coordinator at a local, non-recorded terminal. Reviewers must not receive direct access to the database file or another reviewer's session. Pseudonymous reviewer codes and distinct passphrases prevent one reviewer from seeing a peer decision through the CLI before their own submission. Because a user with direct filesystem or administrator access to the SQLite file can inspect it, the coordinator must keep the protected `ml/data/reviews/` ACL restricted and supervise reviewer access. The CLI does not provide cryptographic isolation from someone who controls the host. Keep terminal transcripts, screenshots, cloud sync, browser extensions and external LLM services away from case text.

Run commands from the repository root. Passphrases are prompted with `getpass` and should never be placed on a command line:

```powershell
backend\venv\Scripts\python.exe -m ml.scripts.review_local init --reviewer-a ReviewerA --reviewer-b ReviewerB --adjudicator Adjudicator
backend\venv\Scripts\python.exe -m ml.scripts.review_local show --reviewer ReviewerA --record-id <64-character-hashed-ID>
backend\venv\Scripts\python.exe -m ml.scripts.review_local review --reviewer ReviewerA --record-id <64-character-hashed-ID>
backend\venv\Scripts\python.exe -m ml.scripts.review_local status --actor ReviewerA --record-id <64-character-hashed-ID>
backend\venv\Scripts\python.exe -m ml.scripts.review_local adjudicate --adjudicator Adjudicator --record-id <64-character-hashed-ID>
backend\venv\Scripts\python.exe -m ml.scripts.review_local export --adjudicator Adjudicator --output ml/data/reviews/evidence-YYYYMMDD.json
```

The first two reviewers independently submit a write-once form. The adjudicator sees both decisions only after both exist, then records a separate final decision. Agreement between reviewers still leaves the case `awaiting_adjudication`. The adjudicator must use a different identity. `status` requires authentication and displays only aggregate state. An evidence export is restricted to the adjudicator, contains all queue IDs and every submitted review event, including pending reviewer codes, timestamps and decisions, but **no narrative text**. It refuses overwrite. Keep the returned SHA-256 with the private review log. A later snapshot must use a new filename; the hash chain plus processed, queue and frozen-split SHA-256 values link snapshots to the underlying decisions and inputs.

## Review rubric

For every case, use the displayed original publisher category, subcategory and privacy flags. Judge only what the redacted record supports:

| Field | Decision rule |
|---|---|
| Authorship | `citizen` only when the text is a citizen complaint narrative; otherwise `staff_note`, `descriptor` or `uncertain`. |
| Identifiers remaining | `yes` for direct or indirect identification risk, `uncertain` when context may identify a person or household, `no` only after manual inspection. |
| Privacy disposition | `approve` only when identifiers remaining is `no`; otherwise `revise`, `exclude` or `escalate`. Never infer consent from the license. |
| Source-category correctness | `yes` only when the original publisher label fits; `no` or `uncertain` for overlap, mismatch or missing labels such as `NULL`. Do not assign a UP department. |
| Verified language | Choose the observed language or script mix; `unknown` when unsupported. |
| Duplicate/template status | `yes` for likely reuse, `uncertain` when unresolved, `no` only after review. |
| Notes | Select controlled reason codes. Free-form text, names, places, numbers and copied narrative excerpts are rejected. |

An `approve` adjudication is accepted only if both independent reviewers marked citizen authorship, no remaining identifiers, correct original category, no duplicate/template concern and privacy approval. The adjudicator must explicitly confirm those points, a meaningful source category and a known language. Other cases remain revised, excluded or escalated. The `eligible` flag is false for every case without that final event. It is a **privacy and source-label gate**, not permission to train or distribute: the owner must still approve retention, the full training set, held-out evaluation protocol and any later distribution terms.

The source resource is [OpenCity/Janaagraha I Change My City 2019–2022](https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f), licensed [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/). Retain publisher attribution and review privacy, attribution and ShareAlike obligations before any distribution. The 30-ID audit is an initial review; it does not clear the other 970 records.
