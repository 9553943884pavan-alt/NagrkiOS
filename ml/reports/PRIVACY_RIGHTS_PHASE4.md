# Phase 4 privacy, rights and retention audit

Reviewed 2026-11-20 without displaying or exporting a citizen narrative. This audit covers the retained 1,000-row OpenCity/Janaagraha candidate extract and the local review workflow. It does not mark any case approved.

## Local storage and schema check

The Phase 3 manifest records the official OpenCity resource, publisher MD5 match, local SHA-256 checksums, 16,071 publisher rows and 1,000 field-minimized selected rows. The full publisher CSV with precise locations was deleted after extraction. Both retained text files are under Git-ignored `ml/data/`; `git check-ignore` confirmed their exclusion. Windows ACL inspection confirmed that inherited permissions are removed on each retained text file and explicit access is limited to the project owner, local sandbox account, SYSTEM and administrators. The 1,000 retained field-minimized rows contain only `record_id`, redacted `title` and `description`, original category/subcategory, agency, creation date and status. **Zero rows had an extra or prohibited column** such as address, latitude, longitude, location, ward, user or staff identifiers. All 1,000 processed rows retain `privacy_status=pending_human_review`.

This is a storage and schema check, not a proof that the narrative text is anonymous. Redacted title and description can still reveal a person or household through context. The local 30-ID review queue contains IDs, category, script hint, split and privacy flags; it should remain outside Git with review decisions. No case excerpt belongs in a report, test fixture, frontend, issue or external LLM request.

## Redaction gap and second-pass result

Aggregate-only **first-pass** screening of the retained redacted titles and descriptions found **7 strings containing URL-like text, 6 containing eight or more consecutive digits, and 43 containing six-digit PIN-like numbers**. These classes were missed by the initial Phase 3 redactor. A second local redaction pass addressed these patterns and regenerated the retained files. The aggregate-only scanner then found **zero matches** in ten direct-identifier patterns across 1,000 minimized rows (2,000 title/description strings) and 1,000 processed complaint-text strings. The patterns cover email, Indian and US phone formats, selected identifier formats, street addresses, URLs, handles, coordinate pairs, eight-or-more-digit strings and six-digit strings. Restricted ACLs were rechecked on both regenerated files. The counts overlap and are not counts of unique people. The existing Phase 3 screening also flagged 30 address patterns, 19 phone patterns, 1 email, 2 handles, 31 possible names and 265 indirect-location cues before replacement/flagging. Names, landmarks, village/ward descriptions, relationships, unusual number formats and combinations of details remain beyond reliable regex detection.

**Review gate:** The refreshed manifest checksum, frozen grouped split and 30-ID queue were revalidated after regeneration. Keep every row pending human review; where the removed full CSV would be needed to resolve ambiguity, exclude or escalate rather than infer. Automated scanning cannot grant privacy approval.

## Publisher license and attribution

The [OpenCity/Janaagraha resource](https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f) identifies the source as Janaagraha iCMyC and labels the resource **CC BY-SA 2.0**. The Phase 3 source report records publisher credits to Vivek Mathew and Haji Shariefullah. The [Creative Commons deed](https://creativecommons.org/licenses/by-sa/2.0/) and [legal code](https://creativecommons.org/licenses/by-sa/2.0/legalcode.en) permit copying and adaptation subject to license conditions. If an adapted dataset is distributed, the legal code requires attribution, the license URI, notice of modifications and compatible ShareAlike terms; it also restricts additional legal or technical barriers inconsistent with the license. **Inference from the legal code:** keeping a private access-controlled review copy is distinct from distributing an adapted dataset. The deed explicitly warns that privacy, publicity or moral rights may still limit use. **The resource license is not proof of consent for every complaint or of ML-training suitability.** Whether future model weights or outputs are derivative works is outside this technical audit and should be assessed before release.

Suggested attribution for any later permitted *distribution* (subject to owner/legal review): Janaagraha iCMyC complaint log 2019-2022, published by OpenCity; credited to Vivek Mathew and Haji Shariefullah; [source resource](https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f); [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/). NagrikOS selected a bounded sample, removed fields and redacted text. Do not publish any text until privacy clearance and distribution terms are approved.

## Owner retention and deletion decisions

The Phase 3 protocol proposes retaining the minimized redacted local text for no longer than needed for review, with a **30-day target from 2026-11-20**. No final owner decision or automatic deletion has been recorded. Before changing retention, the owner should decide:

1. Who may review the redacted local files, whether reviewers need separate Windows accounts, and who controls the review database and backup copies.
2. Whether to keep the 1,000-row minimized text until two-reviewer/adjudication work is complete, with a firm deletion date and any narrow exception for unresolved cases.
3. Which derivatives may be retained after review (approved redacted text, aggregate counts, hashed IDs, provenance), and how excluded/escalated cases and any backup or sync copies will be removed.
4. Whether a future distribution is planned and, if so, the attribution, ShareAlike and privacy review before release.

Until these decisions are recorded, maintain restricted local storage and avoid export. Ordinary file deletion is not a guarantee of secure erasure on SSDs, backups or cloud sync; any deletion procedure should account for those copies. The current count of human-cleared narratives remains **0**.
