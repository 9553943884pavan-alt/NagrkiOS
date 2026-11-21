# Track A Phase 4: original-category pilot proposal

This analysis uses aggregate counts from the verified 1,000-row OpenCity/Janaagraha Phase 3 extract. It does not inspect, quote, relabel, or clear any narrative. **Human-cleared examples: 0.** The source categories remain separate from NagrikOS's 11 demo categories and from any Uttar Pradesh department mapping.

## Source-label support and imbalance

The publisher extract has **32 distinct raw `category_title` values**: 31 usable category names and one literal `NULL` sentinel, now represented as unlabeled in the processed collection. The two largest account for 585/1,000 rows (58.5%); the four largest account for 689/1,000. Eleven labels have at least 20 rows (912 rows in total), while 15 labels have fewer than five rows (27 rows in total). Counts are *before* human privacy and label review; they are upper bounds on usable examples.

| Original source category | Candidate rows | Initial treatment |
| --- | ---: | --- |
| Mobility - Roads, Footpaths and Infrastructure | 340 | Candidate for a narrow source-category pilot, subject to review for mixed traffic/streetlight cases. |
| Garbage and Unsanitary Practices | 245 | Candidate for the same pilot, subject to review for sewerage and other sanitation overlap. |
| Traffic and Road Safety | 53 | Hold out of the first pilot; overlaps road infrastructure and public-safety concepts. |
| Animal Husbandry | 51 | Hold out of the first pilot; distinct source topic but little app-taxonomy relevance. |
| Street lighting | 48 | Review together with `Streetlights` (34); do not automatically merge. |
| Yellow Spot | 41 | Meaning and labeling policy need source-owner/reviewer confirmation before use. |
| Pollution | 29 | Broad concept; review label consistency and potential sanitation overlap. |
| Water Supply and Services | 27 | Review against `Water Supply` (2) before any merge. |
| Sewerage Systems | 24 | Review against sanitation and water service boundaries. |
| Others | 20 | Exclude from scored multiclass evaluation until a reviewer defines its content. |
| Electricity and Power Supply | 19 | Review against `Power supply` (1); both are below the proposed first-pilot support threshold. |
| `NULL` | 1 | Treat as a missing-label sentinel, not a genuine class. Exclude from labeled evaluation. |

Other near-name pairs need explicit review: `Crime and Safety` (10) versus `Safety and Crime` (2), `Public Transport - BMTC` (4) versus `Public transport (BMTC and Metro)` (1), and `Parks & Recreation` (3) versus `Parks & Garden` (1). Similar spelling does not establish identical publisher intent. The aggregate profile reports **two subcategory names under multiple parent categories** and zero exact-text groups with conflicting categories; the latter is unsurprising because all 1,000 selected descriptions are exact-unique. Reviewers should inspect the two subcategory collisions locally without publishing text.

## Smallest defensible category pilot

After every included training and evaluation record passes the documented two-reviewer privacy/authorship/category gate, consider a **two-class source-taxonomy pilot** using only the original `Mobility - Roads, Footpaths and Infrastructure` and `Garbage and Unsanitary Practices` labels. Their current candidate counts are 340 and 245, respectively; **accepted counts are presently 0 and 0**. Keep ambiguous, mixed-topic and mislabeled records excluded rather than forcing either class. Freeze the existing grouped split and audit accepted per-class counts in each partition before any training proposal. If either class has too few accepted held-out examples, reduce scope or collect more genuinely labeled data; do not report an accuracy number from the current unreviewed split.

Use description text available at intake as a possible input only after privacy clearance. Do not feed original category, subcategory, agency, status, later notes, title-derived label clues, or review decisions into the input. The pilot evaluates **OpenCity source-category discrimination**, not NagrikOS category classification or Uttar Pradesh routing. A future expansion to traffic, streetlights, water or sewerage needs written source-label definitions, adjudicated overlap rules, and sufficient approved examples per split. Generated Nandi labels and NYC descriptors cannot fill missing real class support.

## Language and review limits

Every selected OpenCity description has a `latin_script` hint; **zero have human-verified English, Hindi, Kannada, or code-mixed language labels**. The current category-by-script counts are in [PHASE4_LABEL_MATRIX.json](PHASE4_LABEL_MATRIX.json). Do not call that an English-by-category matrix. The refreshed 30-ID local review queue covers 25 source categories, all three splits and every observed privacy-flag type; it is an initial audit and cannot clear the other 970 records. Reviewers should record language, source-label correctness, citizen authorship versus staff/descriptor content, privacy disposition, and possible duplicate/template relationships before any row becomes eligible.

**Current decision: no-go for real-text training or scored evaluation.** The source-grounded labels are promising, but the accepted count is zero until human review. No source label is mapped to a UP department or silently converted into a NagrikOS category.
