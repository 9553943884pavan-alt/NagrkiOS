# ML data preparation tasks

This checklist covers data research only. It does not authorize training or production changes.

- [x] Inspect existing NagrikOS mock ML contracts and category names.
- [x] Audit candidate sources, licenses, access, provenance, and privacy conditions.
- [x] Implement an approved-source HTTPS acquisition allowlist and test retries, bounds, checksums, resume, and reuse.
- [x] Collect a bounded public NYC 311 sample and verify its raw count and checksum.
- [x] Implement explicit-field preprocessing, PII pattern redaction, source-label provenance, and lineage IDs.
- [x] Generate grouped split and held-out review manifests without case text.
- [x] Check processed schema, checksum, coverage, and duplicate isolation.
- [x] Profile source-specific quality and document leakage and privacy limits.
- [x] Propose UP category-to-authority research mapping without authorizing app routing changes.
- [x] Run the offline ML pipeline tests.
- [x] Reevaluate Mendeley tweet rights, privacy, annotations and extraction conditions; leave acquisition blocked.
- [x] Verify Nandi public metadata, Apache-2.0 license and revision; acquire 150 bounded synthetic rows separately.
- [x] Preserve generated category/urgency provenance and 50/50/50 language quota in synthetic manifests.
- [x] Add template-aware split, cross-source leakage audit, exact source-category/language matrix and privacy-safe review IDs.
- [x] Verify OpenCity/Janaagraha narrative fields and CC BY-SA metadata; record bounded API HTTP 403 without downloading records.
- [x] Recheck BBMP and Kaggle source limitations and keep their acquisition disabled.
- [x] Run Phase 2 ML tests, sample validators and backend regression tests.
- [x] Verify the official OpenCity/Janaagraha normal CSV download against publisher MD5, schema and browser origin; do not retry DataStore 403.
- [x] Count 16,071 publisher rows and screen 14,841 narrative-length/category candidates without printing case text.
- [x] Select 1,000 systematic rows, minimize and redact fields, verify SHA-256, then remove the full address/coordinate CSV.
- [x] Restrict local ACLs on retained real-text files and keep all real records Git-ignored.
- [x] Preserve 32 original source labels independently from app categories and leave department/urgency null.
- [x] Generate template-aware grouped split, three-collection leakage audit, source-category-by-script matrix and 30-ID stratified review queue.
- [x] Research CivicAI and other mirrors without treating derivatives or unverified licenses as new independent data.
- [x] Run Phase 3 ML data tests and backend regression tests.
- [x] Harden residual URL, long-number and PIN-like patterns in the retained OpenCity extract; refresh checksums and recheck restricted local ACLs.
- [x] Revalidate the unchanged grouped split and cross-collection duplicate audit after redaction hardening.
- [x] Refresh the 30-ID queue to cover all observed privacy-flag types, all splits and 25 original source categories without narrative text.
- [x] Build a local credentialed two-reviewer and separate-adjudicator workflow with tamper-evident decision events and synthetic integrity tests.
- [x] Produce a source-category pilot proposal and a Phase 4 privacy/rights audit without approving any record.
- [x] Verify frozen Phase 4 processed, manifest, split and queue hashes before Phase 5 screening.
- [x] Screen all 1,000 OpenCity candidates locally with versioned deterministic privacy, authorship, category, language and duplicate triage; keep machine and human fields separate.
- [x] Store checksum-bound case-level screening and a 1,000-ID prioritized plan only in restricted, Git-ignored `ml/data/phase5/`.
- [x] Extend the credentialed reviewer CLI with machine evidence, own-progress/next navigation and post-submission agreement summaries.
- [x] Add synthetic tests for screening, reviewer independence, progress and the training-eligibility gate.
- [ ] Have an independent human quality auditor sample false negatives, indirect identifiers, translation variants and keyword-label disagreement locally; machine checks cannot replace this.
- [ ] Nominate two independent reviewers and one adjudicator, agree retention/access controls, and initialize the protected local decision store.
- [ ] Human-review and adjudicate the first 30-ID queue; treat it as an audit only.
- [ ] Scale the same two-reviewer/adjudication and privacy gate to every candidate proposed for training or evaluation, including held-out examples, before any training request.
- [ ] Freeze model/taxonomy choices before opening held-out evaluation labels; keep evaluation decisions separate from model selection.
- [ ] Obtain documented content reuse and privacy clearance for Mendeley tweet text and BBMP-derived records.
- [ ] Verify Kaggle file schema, primary provenance, and reuse rights before acquisition.
- [x] Obtain a publisher-hash-verified Indian complaint-log corpus with original category labels via the normal OpenCity CSV route.
- [ ] Have two authorized human reviewers inspect the local 30-ID redacted queue for citizen authorship, direct/indirect identifiers, original category accuracy and true language; adjudicate disagreements.
- [ ] Decide retention and handling of the field-minimized redacted local text, and review CC BY-SA attribution/share-alike before any adapted data distribution.
- [ ] Obtain independently labeled real non-complaint intake text for binary detection evaluation.
- [ ] Approve ambiguous UP jurisdiction and department mapping with responsible officials.
- [ ] Have human reviewers examine sampled records, redaction misses, category definitions, and closure semantics.
- [ ] Acquire representative positive and negative intake examples before complaint detection evaluation.
- [ ] Obtain reviewed urgency/safety labels and dated UP outcomes before severity or ETA evaluation.

Restricted sources: CPGRAMS case text and movement APIs are excluded. Conditional sources remain disabled in `configs/sources.json`.
