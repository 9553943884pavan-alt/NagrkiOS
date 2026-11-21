# Phase 5 protected human-review plan

The local, no-text plan at `ml/data/phase5/review_plan_v3.json` holds all **1,000 hashed IDs** in priority order, with original split and source-category metadata. It is restricted by Windows ACL and ignored by Git. The Phase 4 **30-ID audit queue remains unchanged** and should be reviewed first. The plan does not initialize accounts or a decision database.

| Batch | Records | Purpose |
| --- | ---: | --- |
| `audit_30` | 30 | Existing stratified 30-ID audit across 25 categories, 13 flagged IDs and all splits |
| `high_privacy_or_exclusion` | 272 | Highest privacy concern outside the initial audit |
| `ambiguous_quality_or_label` | 501 | Uncertain privacy/authorship, keyword-label mismatch or duplicate candidate |
| `pilot_candidate` | 148 | Remaining two-class pilot candidates for balanced human inspection |
| `representative_low_risk` | 49 | Remaining lower-detected-risk examples; still full human review |

The batches are mutually exclusive and total 1,000; risk counts across the whole corpus are in the [risk summary](PHASE5_PRIVACY_RISK_SUMMARY.md). The 30 audit cases take precedence even when they are high-risk. Reviewers should first record privacy and authorship decisions, then source-label correctness and verified language. A narrow `next`/`progress` command in the Phase 4 CLI shows an authenticated reviewer only their own submitted count and next prioritized hashed ID. The case view now shows machine evidence codes and provisional category/language cues as unverified suggestions. After two submissions, the adjudicator sees a field-by-field agreement/disagreement summary; no peer decision is visible through the reviewer CLI before both independent submissions. The Phase 4 authenticated metadata-only evidence export and tamper-evident event chain remain in place.

**Owner gate:** Before any real review store is initialized, assign two independent human reviewers and a separate adjudicator, decide how they access a supervised local workstation or separate OS accounts, and approve the retention/deletion plan. Passphrases must be entered at prompts, not on command lines. The local SQLite store is not a defense against someone with direct same-account filesystem or administrator access; restrict and supervise that access.

After those decisions, the existing [Phase 4 CLI instructions](REVIEW_LOCAL_PHASE4.md) apply. To review all 1,000 instead of only the 30-ID audit, the coordinator can create a separate store with the Phase 5 queue: `backend\venv\Scripts\python.exe -m ml.scripts.review_local --db ml/data/reviews/opencity_phase5.sqlite3 init --queue ml/data/phase5/review_plan_v3.json --reviewer-a <code> --reviewer-b <code> --adjudicator <code>`. Use the `--db` option before the subcommand for every later call. The coordinator must avoid duplicate human work between the separate 30-ID and 1,000-ID stores; a single 1,000-ID store can use the first 30 as its initial audit. No actual reviewer codes or store have been created.

The reviewer submits one write-once structured decision per ID. Even agreement stays pending until a separate human adjudicator acts. The 30 audit decisions cannot clear the other 970. An approval requires both reviewers to confirm citizen authorship, no remaining identifiers, a correct original category, no duplicate concern, and privacy approval, followed by adjudicator confirmation and verified language. `training_eligibility` remains false without later project-owner approval. Training and scored evaluation are outside this phase.
