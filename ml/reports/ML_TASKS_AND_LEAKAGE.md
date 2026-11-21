# ML task suitability and leakage plan

Research date: 2026-11-20. This is a preparation-stage evaluation protocol. It does not report model performance or authorize training. The existing backend returns deterministic keyword and heuristic results from `backend/app/ai.py`; `backend/app/data.py` says its category and department assignments are illustrative. The API `POST /api/ai/analyze` adds similarity candidates only from accessible local complaints in the same category and district. It is not a trained classifier or semantic search system.

| Task | Minimum genuine evidence needed | Evaluation readiness |
| --- | --- | --- |
| Complaint detection | Real complaints plus representative non-complaint text from the same intake channels, with independent labels. | Conditional. A complaint-only corpus cannot measure false positives. |
| Category classification | Text and a source-provided or human-reviewed issue label with a documented crosswalk to NagrikOS categories. | Conditional. Do not treat keyword-generated app categories as ground truth. |
| Department routing | Official, current jurisdiction/asset ownership and human-confirmed destination for each case. | Blocked until authorized UP routing policy and labels exist. NYC agency names are not UP targets. |
| Urgency/safety | Human-reviewed severity labels, clear emergency exclusion, and error-cost review. | Blocked for automatic action; safety cases require human review. |
| Similarity/duplicate detection | Related-case pair judgments or defensible shared case IDs; hard negatives. | Conditional. Character similarity alone is not evaluated ground truth. |
| Resolution ETA | Genuine creation/closure timestamps, censoring and reassignment histories, and a definition of resolution. | NYC can benchmark methodology within NYC; cannot validate UP ETA. |
| Trends/backlogs | Source timestamps, statuses, reporting coverage, sampling design. | Descriptive within the source only; no UP population estimate from another city. |
| Vision/speech | Labeled civic images or reviewed transcripts with processing rights. | Not evidenced by text datasets. App photo behavior uses filename hints; browser speech is external to ML pipeline. |

## Split and lineage rules

- Assign a stable, source-scoped record ID and keep original source labels in their own fields. Generated suggestions are separate, nullable fields with algorithm/version provenance.
- Remove or redact personal data before committing or distributing text. Raw copies require verified license and access control; never place real citizen text in repository fixtures.
- Normalize text for exact-duplicate detection (Unicode normalization, whitespace, case) while retaining the privacy-safe original wording in cleaned data. Flag near-duplicates using similarity on normalized text, then review samples before treating them as the same event.
- Form groups from explicit linked IDs, duplicates, near-duplicates, reposts, and templated reports. Assign each group to exactly one split. If source location/time is known, use source-aware and preferably chronological held-out evaluation; document the resulting shift and class counts.
- Keep related source versions and recrawls together. Avoid random row-level splitting across versions. If multiple cities or systems are combined, report results by source and city, and hold out an entire source or geography for transfer tests.
- Strip ticket IDs, resolution text, assignee/department fields, final status, closure times, and post-submission notes from inputs for intake-time category/routing/urgency tasks. Retain them only as separately validated targets or metadata. Future timestamps and later edits cannot be features for an intake prediction.
- For ETA research, distinguish unresolved/right-censored cases from observed closures; do not fill missing closure times with SLA targets. Do not use category-specific demo `sla_hours` as a real label.
- Freeze a manifest of held-out group IDs and hashes before modeling, then deduplicate *across* train, validation, and test as a required gate. Include reviewed annotation samples from each source and split.
- Never include the 520 or other synthetic app complaints in real-world evaluation. Synthetic data may test pipeline behavior only.

## Current limits and next gate

No task is presently supported by measured accuracy. Public records may support limited text classification or operational benchmarking once provenance, license, privacy, and label quality pass source-specific review. UP routing, safety decisions, and ETA claims remain blocked without official policy and genuine labeled outcomes. The source audit and collection manifests should determine which of these conditional tasks can advance; no cross-source relabeling is automatic.
