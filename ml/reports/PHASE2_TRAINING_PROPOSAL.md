# Phase 2 training readiness proposal

Prepared 2026-11-20 from the verified local manifests and [machine-readable label matrix](PHASE2_LABEL_MATRIX.json). This is a proposal; **no model was trained or deployed**. The strongest task supported by collected **real** data is NYC-only operational category/agency and closure-method analysis. No collected real citizen narrative supports an Indian complaint-text model yet.

## Exact inventory and independent labels

| Collection | License and provenance | Rows | Usable real citizen narratives | Label status |
| --- | --- | ---: | ---: | --- |
| [NYC 311 bounded sample](https://data.nyc.gov/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9) | [NYC Open Data unrestricted use](https://www.nyc.gov/opendata/get-started/FAQs); public API; cached Phase 1 checksum | 1,000 | 0 | Source issue descriptor, complaint type and NYC agency are real operational metadata, but descriptor text is a categorical label, not an independent complaint narrative. |
| [Nandi synthetic subset](https://huggingface.co/datasets/LatentAILabs/nandi-grievance-synthetic) | Apache-2.0 in public metadata; pinned revision and checksums in [source report](NANDI_PHASE2.md) | 150 | 0 | 120 generated complaint-domain records and 30 generated `none.out_of_scope` records. All category and P1/P2/P3 urgency labels are generated, with **0 human-reviewed labels**. |
| Mendeley, OpenCity/Janaagraha, BBMP, Kaggle | Rights/access/provenance blockers in [source audit](SOURCE_AUDIT.md) | 0 | 0 | No collected labels. |

**Real Indian complaint narratives: 0. Independently labeled real complaint-detection examples: 0. Independently labeled real category examples: 0. Human-reviewed real urgency examples: 0.** The 1,000 NYC records have genuine operational fields, but none has narrative input for this text-learning proposal.

## Category and language matrix

Nandi has 50 `en`, 50 `hi`, and 50 `hinglish` synthetic rows across **45 original source categories**; 30 `none.out_of_scope` examples are distributed 10 per language. The [exact source-category × language counts](PHASE2_LABEL_MATRIX.json) preserve all 45 original labels. NYC has 45 source complaint-type labels, but its language field is only a Latin-script hint from descriptors; it is not a verified English-language narrative count.

| NagrikOS category | Genuine independently labeled real narratives (English / Hindi / Hinglish) | Possible Nandi source examples (generated; original labels retained) | Crosswalk status |
| --- | --- | --- | --- |
| Roads & Infrastructure | 0 / 0 / 0 | `gov.roads_transport`: 0 / 1 / 0 | Ambiguous transport versus road asset; not approved. |
| Water Supply | 0 / 0 / 0 | 0 identified in this subset | No mapping. |
| Electricity | 0 / 0 / 0 | 0 identified | No mapping. |
| Sanitation & Waste | 0 / 0 / 0 | 0 identified | No mapping. |
| Healthcare | 0 / 0 / 0 | `gov.health_hospitals`: 2 / 2 / 1 | Candidate only; facility and jurisdiction need review. |
| Education | 0 / 0 / 0 | 0 relevant public-school examples identified | Private coaching is not a Basic Education label. |
| Women & Child Services | 0 / 0 / 0 | 0 identified | No mapping. |
| Land & Revenue | 0 / 0 / 0 | 0 identified | No mapping. |
| Public Safety | 0 / 0 / 0 | 0 identified | No mapping or safety ground truth. |
| Social Benefits | 0 / 0 / 0 | `gov.ration_pds`: 1 / 1 / 1 | Scheme-specific; food/civil supplies authority needs review. |
| Other | 0 / 0 / 0 | 0 approved | `none.out_of_scope` is a generated non-complaint group, not NagrikOS Other. |

The table does **not** relabel any record into an app category or department. It shows only possible lexical overlaps requiring human review. Most Nandi labels concern railways, LPG, banking, insurance and consumer matters outside the current UP municipal-demo taxonomy. The [UP authority mapping proposal](LABEL_MAPPING_REVIEW.md) remains unapproved.

## Task decisions

| Task | Current evidence | Reasonable next action |
| --- | --- | --- |
| Real-data operational analytics | 1,000 NYC source records with agency, category, status and dates; 998 closure pairs. | Descriptive NYC-only analysis and method prototyping after source semantics/selection-bias review. No UP generalization. |
| Complaint detection | 120 synthetic complaint-domain vs 30 synthetic `none` rows, generated labels only. | An **experimental synthetic-only baseline** could be specified later, but do not train in this phase or claim real-world accuracy. Need representative independently annotated real positives and negatives. |
| Category classification | 45 synthetic source categories, many with 1–3 examples; 0 genuine narrative labels in NagrikOS categories. | Not ready for a NagrikOS classifier. Consider source-taxonomy experiments only after sufficient examples and a genuine held-out set. |
| Routing | 0 official UP jurisdiction/department labels. | Keep human-reviewed policy/rules. Obtain authorized desk/asset ownership map and real routing outcomes. |
| Urgency/safety | Synthetic P1/P2/P3 labels only, 0 reviewed severity examples. | No safety model or automated prioritization proposal. Define annotation policy and human escalation first. |
| Resolution ETA | NYC operational intervals only; 0 representative UP closure histories. | Method research only; account for open cases, censoring, reassignment and source bias. |
| Similarity | Template-aware split guard passed; no judged related-case pairs. | Obtain human pair labels before model evaluation. |

The 150 synthetic cases have a template-aware 109/16/25 split. This does not create an independent real test set. A cross-source audit against the cached NYC sample found 0 detected related groups across sources and 0 across split boundaries; multilingual paraphrases and unseen templates still require review. No training/evaluation accuracy is claimed.

## Decisions requiring owner approval or external access

1. Request an authorized, field-minimized OpenCity/Janaagraha export or working API access for the CC BY-SA 2.0 complaint log. The bounded API returned HTTP 403; exclude address, coordinates and person metadata at source. Review narrative quality and privacy before using it.
2. If Mendeley tweet text remains desired, obtain a documented rights/privacy determination, a text-only lawful extraction method, and a deletion/update process. Its CC BY 4.0 deposit alone did not clear full-text use; `unknown` needs label review.
3. Approve an annotation protocol and human review sample for genuine complaint/non-complaint, category, privacy and safety labels. The existing ignored 15-ID Nandi sample is for synthetic quality review only.
4. Approve UP category-to-authority mappings with officials before any routing use. Bengaluru and NYC labels cannot establish UP desk ownership.

No production PostgreSQL, FastAPI endpoint, frontend, authentication, or deployed ML behavior was modified.
