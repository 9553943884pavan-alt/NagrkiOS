# Dataset readiness

## What is ready

- Source provenance, public reuse evidence, bounded query, checksum, count, schema, and reproducible acquisition are recorded for one NYC 311 sample.
- Offline normalization, explicit source-label preservation, basic redaction, quality profiling, grouped split and integrity tests run without changing the NagrikOS app.
- NYC-only operational questions can be explored after a human check of source status/closure semantics and selection bias. The sample supports workflow and pipeline validation, not any accuracy claim.

## What is not ready

| NagrikOS feature | Decision |
| --- | --- |
| Indian complaint detection | No real Indian narrative plus non-complaint corpus with approved reuse and labels. Keep mock or manual handling. |
| Category classification | NYC descriptor is effectively a category label; using it as input leaks the target. No eligible Indian text/category pairs collected. Keep current demonstration logic. |
| UP department routing | NYC agency labels have no UP jurisdiction validity. UP proposed mapping remains ambiguous and unapproved. Keep human-authorized routing; do not train or replace existing rules from this data. |
| Urgency and safety | No reviewed severity labels or safe negative cases. Keep human review and emergency exclusions. |
| Resolution-time suggestion | NYC dates can exercise methods only; no representative UP outcome history or censoring model. Keep estimates clearly illustrative. |
| Similarity | Exact and near-duplicate grouping is a split guard, not a measured duplicate-detection model. |

The prepared `complaint_text` field is tagged `text_kind=descriptor_label` for every NYC row. No cleaned **real** Indian complaint-text dataset exists yet. The 460/505/35 held-out split is leakage checked but unsuitable for model evaluation because only 66 unique descriptor strings are present. The 15-ID annotation review manifest awaits human inspection. No model was trained, and all existing app ML outputs remain simulated.

## Decisions needed from the project owner

1. Provide documented reuse/privacy permission or an acceptable substitute for Indian citizen narratives, especially Mendeley social-media text and BBMP-derived records.
2. Confirm UP jurisdiction/asset ownership rules and approve or revise ambiguous mappings with responsible officials.
3. Arrange human review of privacy, category meaning, and closure semantics; obtain ground-truth severity and outcome labels for any later safety or ETA research.

See `SOURCE_AUDIT.md`, `LABEL_MAPPING_REVIEW.md`, `DATA_QUALITY.md`, `PRIVACY_AUDIT.md`, and `ML_TASKS_AND_LEAKAGE.md` for evidence and limitations.

## Phase 2 update

The new [training-readiness proposal](PHASE2_TRAINING_PROPOSAL.md) and [exact label matrix](PHASE2_LABEL_MATRIX.json) supersede the Phase 1 acquisition counts above. A separate Apache-2.0 Nandi synthetic subset adds 150 generated narratives (120 complaint-domain, 30 out-of-scope) across English, Hindi and Hinglish. It adds **no genuine real complaint narrative and no independently reviewed label**. The only collected real data remains the 1,000-row NYC operational sample. Mendeley full-text use remains blocked by unresolved platform/privacy rights; OpenCity/Janaagraha's licensed real-text resource returned HTTP 403 to a bounded field-selected request. Category, routing, urgency and ETA readiness decisions above remain unchanged for production use.

## Track A Phase 3 update

The [official OpenCity/Janaagraha CSV](OPENCITY_PHASE3.md) was verified against the publisher's hash through the normal browser download route, distinct from the earlier blocked DataStore API. A bounded, field-minimized extract now contains 1,000 **candidate real descriptions** with 32 original source categories. The [Phase 3 source-label matrix](PHASE3_LABEL_MATRIX.json) lists counts by category and Latin-script hint. **Zero** rows have a completed human privacy disposition or verified language; therefore **zero** are currently usable as a reviewed real-text evaluation set. The full CSV with precise locations was removed. Binary complaint detection still lacks real negative examples. Source-taxonomy classification is conditional on privacy, authorship and label review; UP routing, safety urgency and ETA remain unsupported. See the [suitability protocol](REAL_TEXT_SUITABILITY_PHASE3.md) and [privacy audit](PRIVACY_AUDIT.md).

## Track A Phase 4 update

The [human-review gate](PHASE4_REVIEW_GATE.md) and [offline reviewer workflow](REVIEW_LOCAL_PHASE4.md) are ready for authorized humans. Residual URLs, long numbers and PIN-like strings found by a second automated screening were redacted locally; the processed manifest and checksum were updated and the frozen grouped split revalidated. The 30-ID audit queue was refreshed to cover all observed privacy-flag types, 25 source categories and all three splits. The current [Phase 4 matrix](PHASE4_LABEL_MATRIX.json) reflects 31 named source categories and one unlabeled `NULL` sentinel. This is still **1,000 candidates, 0 human-reviewed, 0 cleared, 0 excluded**, and no reviewed category-by-language cells. The 30-ID audit cannot clear the other 970. No real-text training or scored evaluation is authorized.
