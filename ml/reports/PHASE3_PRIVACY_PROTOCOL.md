# Track A narrative privacy and retention protocol

Prepared before processing any new citizen narrative. The OpenCity/Janaagraha resource advertises title, description, category/subcategory, agency, creation date and status, alongside precise address, location, ward and coordinates. The latter fields are excluded from the research collection. A publisher CSV has no complaint ID column in its header; local record IDs must therefore derive from the verified file checksum and CSV row ordinal, with that limitation recorded in provenance.

## Collection boundary

1. Confirm the file came from the official, openly offered resource download and verify publisher/license before parsing case rows. Do not work around a 403 API response.
2. Place any full publisher CSV only in ignored `ml/data/raw/opencity_unreviewed/` while verifying. Never commit or print source rows. Record its SHA-256, byte length, actual CSV row count and header schema as metadata only.
3. Stream the file into an ignored, bounded **field-minimized** collection. Retain only a hashed local case ID, title, description, original category/subcategory, original agency, creation date and status. Do not copy `address`, `location`, latitude, longitude, ward IDs/titles, comments, staff/person data or other metadata. The original download should be removed after selected-field checksum and count verification, leaving its checksum/provenance in the manifest.
4. Redact both the field-minimized local copy and the processed JSONL. Direct email, phone, selected identifier and street-address patterns are replaced with placeholders. Flag possible names, landmarks, ward/village references, unusual identifiers and all surviving narratives for **human privacy review**; regex checks do not certify deidentification.
5. Keep original labels in `category` and `source_subcategory` with `category_source=source_provided`. Preserve original agency as source metadata, never as a UP department target. Missing labels remain null. Do not create urgency, closure, complaint/non-complaint or translated labels.

## Access and review

All raw, processed, split and review-ID files stay under Git-ignored `ml/data/`. The two retained text files have inherited Windows permissions removed; their explicit ACL permits the project owner, the local sandbox account, SYSTEM and administrators. Git ignore alone is **not** an access control. Do not upload narrative text to external LLMs or include case excerpts in reports. Reviewers should inspect a small local sample of redacted text. The full unredacted publisher CSV was removed, so uncertain redactions must be excluded or resolved through an authorized publisher/reviewer process rather than inferred. Record only aggregate decisions publicly.

Until that human review is completed, new records are **candidate narratives**, not privacy-cleared training/evaluation examples. Keep the field-minimized redacted local copy no longer than needed for review (target: 30 days), then securely remove it per the owner's retention decision and preserve only approved derivatives and non-sensitive manifests. If approval or lawful use cannot be confirmed, delete the new narrative collection rather than using it. No production data or application service is part of this process.

## Actual Phase 3 screening

The publisher CSV contained 16,071 rows; 14,841 passed the minimum description-length and original-category criterion, and 1,000 were systematically selected. The full CSV was removed after the retained files' SHA-256 checks passed. The redactor flagged 30 selected rows with address patterns, 19 with phone patterns, 1 with email, 2 with handles, 31 with possible names and 265 with possible indirect location cues; a row may have multiple flags. The 30-ID stratified review queue covers 29 source categories, all three research splits and 11 flagged records. **Zero** records have received a human privacy disposition. These counts describe screening signals, not a proof that all other rows are free of personal information.
