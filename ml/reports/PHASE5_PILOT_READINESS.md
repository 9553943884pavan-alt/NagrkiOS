# Phase 5 source-category pilot readiness

**No-go for training or scored evaluation.** The two-class proposal concerns original OpenCity/Janaagraha categories, not NagrikOS categories or Uttar Pradesh routing. No human reviewer has submitted a decision, and no record is training-eligible.

| Original publisher category | Train candidates | Validation candidates | Test candidates | Human-cleared train / validation / test |
| --- | ---: | ---: | ---: | --- |
| Mobility - Roads, Footpaths and Infrastructure | 227 | 54 | 59 | 0 / 0 / 0 |
| Garbage and Unsanitary Practices | 164 | 41 | 40 | 0 / 0 / 0 |

Within Roads, machine privacy triage found 85 high, 84 uncertain and 171 low-detected-risk cases. Within Garbage, it found 83 high, 48 uncertain and 114 low-detected-risk cases. None of these buckets is a clearance. Source labels are publisher-provided but not independently verified, and every intended train, validation and test record requires two human reviews plus separate adjudication. The 30-ID audit is only an initial quality check for the larger 1,000-record corpus.

Keep the grouped split frozen. Decide class definitions, exclusions, features and thresholds from training/validation only, before a separate evaluator opens the held-out test partition for scoring. Privacy review may inspect test records, but test text or label disputes must not drive model/taxonomy selection. Real non-complaint negatives are absent, so binary detection is also not ready. No UP department, urgency, safety or ETA ground truth was acquired.

Before requesting training approval, report accepted records by original source class, human-verified language and split; resolve duplicate/translated-variant risks across partitions; document exclusion reasons; freeze the evaluation protocol; and obtain project-owner approval of retention, rights and scope. CC BY-SA 2.0 publisher attribution is retained, while privacy consent and future distribution obligations remain separate unresolved decisions.
