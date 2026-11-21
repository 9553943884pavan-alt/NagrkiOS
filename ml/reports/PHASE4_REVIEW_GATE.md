# Track A Phase 4: human-review and evaluation gate

Status on 2026-11-20: **no-go for real-data model training or scored evaluation**. All 1,000 OpenCity records are candidates; **0 reviewed, 0 human-cleared, 0 excluded and 1,000 uncleared**. The 30-ID queue is ready for authorized reviewers but contains no submissions. The other 970 records remain outside this initial audit and cannot inherit its decisions.

## Frozen inputs and measured checks

| Item | Result |
| --- | --- |
| Retained OpenCity narratives | 1,000 minimized, redacted candidates; 1,000 unique normalized texts |
| Grouped split | 676 train, 157 validation, 167 test; SHA-256 `c58aa51f60bf174b3262694ab2153ce22398d70bef2713607b0d1603a18c24f0` |
| Refreshed 30-ID audit queue | 21 train, 5 validation, 4 test; 25 source category names, 13 flagged IDs; SHA-256 `6a6e7875d8d057316f994b8fb8353b168f54d60ed7e2461844ed353376a6ab32` |
| Privacy coverage in queue | Every observed flag type: address, email, handle, long_number, phone, pin_like, possible_location, possible_name, url |
| Post-hardening processed file | SHA-256 `a9e2306b635e7b6d554c314893e016b3349619d853cb857db99b035bb51f2ccd` |
| Duplicate audit | 0 cross-source related groups, 0 cross-split related groups; 1,000 OpenCity related groups for 1,000 rows |
| Direct-pattern scan | 0 matches across ten scanner patterns after hardening; this is **not** privacy clearance |
| Original source labels | 31 named categories plus one `NULL` sentinel, kept as an unlabeled record; zero human-verified labels or languages |

The queue and retained text are under Git-ignored `ml/data/` with restricted Windows file permissions. The audit queue has hashed IDs and metadata only. The review tool is an offline command-line program: it starts no HTTP server, binds no port, sends no telemetry and makes no LLM request. It reads redacted text only for a specifically requested queue ID after local reviewer authentication. The source category and subcategory are displayed separately from the text. Structured reviewer fields cover authorship, remaining identifiers, privacy disposition, source-category correctness, verified language, suspected duplicate/template and controlled reason codes. No free-form excerpt or location belongs in a decision.

Two distinct reviewer identities must submit separate, write-once decisions. Before adjudication, a reviewer cannot retrieve the other review through the CLI. A distinct adjudicator sees both decisions only after both submissions and records an explicit resolution. No record is approved automatically. The event store uses timestamps and a hash chain; an authenticated adjudicator can write a no-text, write-once evidence snapshot with decision codes and source checksums. These controls detect ordinary modification and refuse overwrites, but local administrators and backups remain in the trust boundary; they are not a claim of cryptographic immutability against an administrator. Reviewers must use supervised access or separately controlled workstations/accounts rather than receiving unrestricted shell or file access to the decision database.

## Acceptance rubric

A record counts as human-cleared only when the two distinct reviews both identify citizen-authored text, no remaining direct or indirect identifiers, source-category correctness and no duplicate/template concern, and both approve its privacy disposition. The separate adjudicator must explicitly approve with the same safe findings, a meaningful publisher category and a verified language. `uncertain` is not approval. Any staff note, descriptor, missing source label, identifier, ambiguous category or unresolved duplication is revised, excluded or escalated. The single `NULL` source category cannot be a scored class. Approved decisions remain local and do not by themselves authorize training or distribution.

The 30 cases are a **sampling audit**, not a batch release. For every later training or evaluation record, repeat the same two-reviewer/adjudication process, including all held-out records. Expand review by category, privacy-risk group and split until each intended class has sufficient accepted examples in each partition. Do not promote the existing 30 decisions to the other 970. Record exclusion reasons and approved counts by original category and verified language after actual human work.

## Evaluation discipline

Keep the frozen grouped split and source provenance. Decide the source-category taxonomy, model inputs, thresholds and pilot scope from training/validation evidence only. The four test IDs in the audit queue may receive privacy and source-label review, but their text, labels and outcomes must not guide feature, taxonomy or hyperparameter selection. A separate evaluator should hold the test partition until the design is frozen and then report accepted test counts and exclusions without cycling back to model selection. The first source-category proposal is limited to `Mobility - Roads, Footpaths and Infrastructure` (340 candidates) and `Garbage and Unsanitary Practices` (245 candidates); both currently have **0 accepted**. The 31 named original categories remain separate from NagrikOS app categories and Uttar Pradesh departments.

Real complaint detection still lacks independently labeled non-complaint intake examples. Source-category classification has promising genuine source labels but remains blocked by human privacy/authorship/category clearance. Neither this Bengaluru dataset nor the synthetic Nandi labels support UP department routing, safety urgency or resolution-time claims.

## Owner decisions before review and later use

1. Name two independent authorized reviewers and a distinct adjudicator, control their local access and passphrases, and decide who retains encrypted/local backups of the ignored decision store.
2. Approve a definite retention/deletion date and procedure for the 1,000 redacted records, exclusions, derived decisions and backup/sync copies. The current 30-day target is a proposal, not an owner decision.
3. Before any later distribution, review CC BY-SA 2.0 attribution, modification notice, ShareAlike and complaint privacy conditions. Internal review does not grant broad permission to publish text or model artifacts.
4. Approve any later training/evaluation pilot separately, after per-class accepted counts and a frozen evaluation protocol are documented. No UP departmental mapping is approved here.

See [privacy and rights audit](PRIVACY_RIGHTS_PHASE4.md), [source-category pilot](SOURCE_CATEGORY_PILOT_PHASE4.md) and [local reviewer instructions](../README.md).
