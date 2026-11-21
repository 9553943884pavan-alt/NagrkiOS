# Nandi synthetic corpus: Phase 2 source and sample record

Reviewed and collected 2026-11-20 UTC. The [publisher's Hugging Face dataset card](https://huggingface.co/datasets/LatentAILabs/nandi-grievance-synthetic) describes an entirely synthetic corpus written with open-weight language models, with generated category and urgency labels. The public [Hugging Face dataset metadata API](https://huggingface.co/api/datasets/LatentAILabs/nandi-grievance-synthetic) returned `private=false`, `gated=false`, `license:apache-2.0`, revision `cf76fd674a7bf03c770a92eaca0e81825cb949fc`, and `train.jsonl` / `test.jsonl`. The card attributes the release to Arun Prabhakaran and states Apache 2.0. These are publisher claims, not independent verification of generation quality.

The [dataset viewer's `/rows` API](https://huggingface.co/docs/dataset-viewer/rows) exposed fields `id`, `text`, `category`, `domain`, `urgency`, `language`, `channel`, `persona`, `tone`, `generation`, `writer`, `checker_urgency`, and `p1_consistent`. The release claims 116,199 train and 2,985 test rows across English, Hinglish and 11 other Indian languages. The sample below uses **train only**, and retains only `id`, `text`, `category`, `domain`, `urgency`, and `language` in ignored raw storage. No persona, channel, account metadata, location or model-internal fields are retained.

## Actual bounded collection

`ml/scripts/acquire_nandi.py` requested nine 100-row pages at systematic train offsets 0, 14,500, 29,000, 43,500, 58,000, 72,500, 87,000, 101,500 and 116,000 through the public viewer. It checked the source revision before and after collection, checked the Apache 2.0 tag, then selected at most 50 rows per language with deterministic quotas: 20 `gov`, 10 `none`, and 20 other domains. No quota was short. This is a **quota sample**, not a population-representative sample. A repeated run verifies and reuses the manifest and checksums without network access.

| Artifact | Rows | SHA-256 | Storage |
| --- | ---: | --- | --- |
| Minimal raw selected JSONL | 150 | `53d9f1f517aadaa442f61ae5be050111e26c01dcddf1981cefcfe397baf8c5ef` | Ignored `ml/data/raw/nandi_synthetic_phase2/selected.jsonl` |
| Normalized and redacted JSONL | 150 | `c4d60f63e7d82a064e5814783ee11dc57aac2e746dc7063e9e318c4894f2d618` | Ignored `ml/data/processed/nandi_synthetic_phase2.jsonl` |
| Template-aware split manifest | 150 IDs | `948f8bf2506606668813e8c8b5a577408beccfc85e0515b871bd0dc16bdf8fac` | Ignored `ml/data/evaluation/nandi_synthetic_phase2.split.json` |

The full provenance, page counts, revision, selection quotas and checksums are in ignored `ml/data/manifests/nandi_synthetic_phase2.json`. The processed schema sets `data_kind=synthetic`, `text_kind=synthetic_narrative`, `category_source=synthetic_generated`, `urgency_source=synthetic_generated`, and retains the original `source_domain`. A 15-ID review sample is in ignored `ml/data/evaluation/nandi_synthetic_phase2.review.json`; it contains no text.

## Actual labels and coverage

The sample contains 50 `hi`, 50 `hinglish`, and 50 `en` rows. Each language has 20 `gov`, 10 `none` (generated non-complaints), and 20 bank/insurance/consumer/telecom rows. There are 45 distinct source categories overall, including `none.out_of_scope`; English covers 23, Hindi 25, and Hinglish 26 category values. The urgency distribution is P1=26, P2=37, P3=87, all **generated labels**. No category, complaint/non-complaint, urgency or safety label has been independently human-reviewed. The 150 texts are distinct under normalized exact comparison; the template-aware split contains train=109, validation=16 and test=25, but template families may still evade automated matching.

Direct overlap with NagrikOS's broad demo categories is sparse. The sample has `gov.health_hospitals` (5) as a possible healthcare example, `gov.roads_transport` (1) as an ambiguous roads/transport example, and `gov.ration_pds` (3) as a scheme-specific social-benefits example. These are **candidate crosswalks only**: Nandi's national/regulator taxonomy is not a verified Uttar Pradesh category or department label. Other 51 government-domain examples cover such topics as railways, LPG, passport and pension administration that do not map cleanly to the current NagrikOS taxonomy. No NagrikOS category was assigned to these records. See `NANDI_SAMPLE_PROFILE.json` for aggregate source-label distribution.

## Appropriate use and limits

- The synthetic positives and negatives can support pipeline prototyping or an experimental complaint-detection baseline. They cannot establish real-world detection performance.
- The generated source categories could support exploratory pretraining on Nandi's **own taxonomy**, but most NagrikOS categories lack direct, independent labels in this subset. Do not use an automatic crosswalk as ground truth.
- Generated urgency P1/P2/P3 values are **not verified safety labels** and must not drive emergency or service priority decisions. No UP department, status or closure-time target exists.
- The publisher itself warns that synthetic writing is cleaner and more explicit than real complaints and that generated labels are not human labels. A genuine, independently labeled held-out Indian intake corpus is required before any performance claim.

Verification: four focused `test_nandi.py` tests passed; `ml.scripts.validate` passed on all 150 records and the template-aware split. Raw and processed text remain ignored by Git. The existing backend and frontend were not modified.
