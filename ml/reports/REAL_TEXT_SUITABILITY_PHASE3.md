# Track A real narrative suitability and evaluation contract

The NagrikOS backend currently has 11 broad demo categories in `backend/app/data.py`. `backend/app/ai.py` uses deterministic keyword scoring and heuristic urgency/ETA; these are not trained or evaluated models. The OpenCity/Janaagraha source describes Bengaluru complaints. Its original `category_title`, `sub_category_title` and `civic_agency_title` are **publisher metadata**; none is an authorized Uttar Pradesh category, desk, urgency or resolution target. Preserve those fields independently, and leave any proposed NagrikOS crosswalk separate, versioned and unapproved until reviewed on examples.

## Actual sample inventory

The verified publisher CSV contains 16,071 rows. A systematic field-minimized extract selected 1,000 rows from 14,841 entries meeting the current narrative-length and nonempty source-category rule. The [aggregate profile](OPENCITY_SAMPLE_PROFILE_PHASE3.json) reports **32 original category labels**, 1,000 distinct normalized descriptions, 0 detected exact duplicates, and a template-aware 676 train / 157 validation / 167 test split. The top source labels are `Mobility - Roads, Footpaths and Infrastructure` (340), `Garbage and Unsanitary Practices` (245), `Traffic and Road Safety` (53), `Animal Husbandry` (51), `Street lighting` (48), `Yellow Spot` (41), `Streetlights` (34), `Pollution` (29), `Water Supply and Services` (27), and `Sewerage Systems` (24). These are source labels, not app mappings.

All 1,000 selected descriptions have a `latin_script` hint, but **0 have a human-verified language assignment**. The exact category-by-script distribution is the profile's `category_distribution` paired with the universal Latin-script hint. It is not an English-by-category table. The top two source categories hold 585 records (58.5%), while 15 of 32 categories have at most five records; a naive 32-class score would be unstable. More importantly, **0 of the 1,000 candidates is human privacy-reviewed**, so the current count of privacy-cleared, genuinely usable real training/evaluation narratives is **0**. Counts may increase only after the review protocol below is completed and recorded.

## Source-category crosswalk candidates (unapproved)

These suggestions do not change any record's original category and do not imply a responsible UP department.

| Original OpenCity category | Possible NagrikOS category | Review issue |
| --- | --- | --- |
| `Mobility - Roads, Footpaths and Infrastructure` | Roads & Infrastructure | Road/footpath owner and urban jurisdiction vary. |
| `Garbage and Unsanitary Practices` | Sanitation & Waste | Waste collection and sanitation service boundaries need review. |
| `Traffic and Road Safety` | Public Safety **or** Roads & Infrastructure | Enforcement, signals and road defects have different owners. |
| `Street lighting` / `Streetlights` | Electricity **or** Roads & Infrastructure | Lamp maintenance may be municipal, utility or road authority work. |
| `Water Supply and Services` | Water Supply | Urban provider and asset ownership still need confirmation. |
| `Sewerage Systems` | Sanitation & Waste **or** Water Supply | Drainage, sewerage and drinking-water supply are distinct. |
| `Animal Husbandry`, `Yellow Spot`, `Pollution`, `Others` | Unmapped pending review | The app taxonomy has no verified one-to-one equivalent. |

Human reviewers should approve a versioned crosswalk on actual examples and leave uncertain cases unmapped. No source category is a UP department label.

## Label and privacy contract

- Treat a nonempty, narrative-length description with original category as a **candidate real complaint**, subject to provenance, license and privacy review. A CSV field name alone does not prove every row is a genuine citizen-authored submission; sample reviewers should inspect title/description authorship and possible staff notes.
- Keep `category_source=source_provided` and `data_kind=real`. Keep `source_subcategory` and `source_agency` as metadata; set app department and urgency null. The CSV header has no complaint ID, so the local hash of publisher file checksum plus row ordinal is stable for this exact export only. Recrawls need duplicate detection across versions.
- All descriptions retain `privacy_status=pending_human_review` until review is recorded. Automated redaction of emails, phones, addresses and handles is useful screening, but names, indirect locations, and combinations of details can remain. No human-approved training/evaluation count should include pending rows.
- Latin-script hints are **not** verified English labels. A reviewer should identify English, Kannada, transliterated Kannada/Hindi, code-mixed, and unknown examples using text itself. No translation was generated or counted as original writing.

## Task readiness

| Task | Current inference from source fields | Gate before genuine evaluation |
| --- | --- | --- |
| Binary complaint detection | A complaint log supplies candidate positives only. `Rejected` status is not an independently labeled non-complaint. | Acquire representative real negative intake text from the same channels, annotate complaint/non-complaint with written rules and adjudication, then freeze a held-out set. Synthetic Nandi negatives cannot stand in for real negatives. |
| Source-category multiclass classification | Original `category_title` supplies candidate source-grounded labels with a real description; rare labels and annotation errors are possible. | Human audit authorship and label consistency, merge only reviewed duplicate/near-equivalent labels, keep rare classes out of scored claims or collect more data, and evaluate on grouped held-out real text. Train only on description available at intake; do not feed category, subcategory, agency, status or other label proxies into features. |
| NagrikOS-category classification | No approved crosswalk from Bengaluru source labels to the app's 11 categories exists. | Review a versioned source-to-app mapping with human examples per category and explicit unmapped/ambiguous class. Do not treat lexical overlap as ground truth. |
| Department routing, safety urgency, ETA | No authorized UP department outcomes, reviewed severity labels, or genuine closure times. | Remain rule/human controlled. Bengaluru agency/status cannot validate UP routing, safety or resolution time. |

## Leakage-safe split and human-review design

Use the existing template-aware grouped split over normalized descriptions, retaining same/near-duplicate and repeated-template families together. Inspect source titles and descriptions for copied agency boilerplate, repeated staff responses and near-identical templates. A later independent test set should be frozen by source export version and, where sufficient data allows, by later submission dates or another municipality; the current stable-hash split is a **research split**, not evidence of temporal or geographic generalization. Check duplicates across every new export and against train/validation/test before modeling. Do not mix NYC descriptors, Nandi synthetic narratives, and Bengaluru real descriptions into one scoring population.

Create a local review queue sampled across frequent and rare original categories, script hints, privacy flags, duplicate families and each split. Show only redacted narratives to reviewers; the full original CSV was removed after minimization, so unresolved cases require exclusion or a separate authorized publisher/reviewer process. Two independent reviewers should record: citizen narrative versus descriptor/staff note, original category correctness, verified language, direct/indirect identifiers, privacy disposition, possible duplicate family, and whether a proposed app-category mapping is defensible. Resolve disagreements with an adjudicator and retain only aggregate counts and hashed IDs in shared reports. No raw text or review excerpts belong in Git or external LLM APIs.

**Readiness decision:** candidate real narratives can support a source-taxonomy pilot only after privacy and label audit; no scored real-text complaint detection or NagrikOS-category classification is ready before those gates. No model training or deployment occurred in Phase 3.
