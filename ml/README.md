# Offline ML data workspace

This directory holds research data preparation only. The running FastAPI and React app do not import it. Existing classification, routing, urgency, and resolution suggestions remain rule based mock outputs.

`configs/sources.json` is the acquisition allowlist. `data/` is ignored by Git because raw and derived case records may contain personal information. Reports contain aggregate counts and metadata only. Keep local `data/` access limited to authorized researchers; never upload it to an external LLM service.

## Reproduce the approved sample

Run from the repository root in PowerShell with the backend virtual environment:

```powershell
$py = 'backend\venv\Scripts\python.exe'
& $py -m ml.scripts.acquire --source nyc_311_2024_bounded
$entry = Get-Content ml/data/manifests/nyc_311_2024_bounded.json -Raw | ConvertFrom-Json
$raw = Join-Path ml/data $entry.path
& $py -m ml.scripts.preprocess --input $raw --output ml/data/processed/nyc_311_2024_bounded.jsonl --source-id nyc_311_2024_bounded --text-field descriptor --text-kind descriptor_label --id-field unique_key --category-field complaint_type --department-field agency --created-at-field created_date --closed-at-field closed_date --status-field status
& $py -m ml.scripts.split --input ml/data/processed/nyc_311_2024_bounded.jsonl --output ml/data/evaluation/nyc_311_2024_bounded.split.json
& $py -m ml.scripts.validate --processed ml/data/processed/nyc_311_2024_bounded.jsonl --split ml/data/evaluation/nyc_311_2024_bounded.split.json --manifest ml/data/processed/nyc_311_2024_bounded.jsonl.manifest.json
& $py -m ml.scripts.review_sample --split ml/data/evaluation/nyc_311_2024_bounded.split.json --output ml/data/evaluation/nyc_311_2024_bounded.review.json
& $py -m ml.scripts.profile --processed ml/data/processed/nyc_311_2024_bounded.jsonl --split ml/data/evaluation/nyc_311_2024_bounded.split.json --output ml/reports/NYC_SAMPLE_PROFILE.json
& $py -m pytest -q ml/tests
```

Acquisition reuses a verified raw file. Preprocessing reuses an output only when its checksum, source checksum, version, and field mapping match its manifest. Split and review commands refuse to overwrite existing manifests; verify the existing files or choose new versioned output paths for a changed experiment. The report command reproduces aggregate metrics. A live NYC export may change after the pinned collection; compare its new checksum and timestamp with `reports/COLLECTION_SUMMARY.md` before interpreting results.

## Interpretation

The NYC sample has categorical `descriptor` values, not citizen narratives. `complaint_text` is the normalized descriptor solely to fit the common research schema and is tagged `text_kind=descriptor_label`. It is **not suitable input** for complaint-text classification; using it as a model feature would leak the label. NYC agencies are retained as source-provided metadata and never mapped to UP departments. All prepared records retain `privacy_review_required=true` because regex redaction cannot prove the absence of people or addresses.

See `reports/SOURCE_AUDIT.md`, `reports/DATASET_READINESS.md`, and `TASKS.md` for limits and next decisions.

## Phase 2 synthetic subset and readiness audit

The public Apache-2.0 Nandi dataset is acquired by a separate pinned-revision reader. It produces 150 explicitly synthetic records and reuses its verified local manifest on subsequent runs. These commands do not redownload the NYC sample:

```powershell
$py = 'backend\venv\Scripts\python.exe'
& $py -m ml.scripts.acquire_nandi
if (-not (Test-Path ml/data/evaluation/nandi_synthetic_phase2.split.json)) {
  & $py -m ml.scripts.split --template-aware --input ml/data/processed/nandi_synthetic_phase2.jsonl --output ml/data/evaluation/nandi_synthetic_phase2.split.json
}
& $py -m ml.scripts.validate --processed ml/data/processed/nandi_synthetic_phase2.jsonl --split ml/data/evaluation/nandi_synthetic_phase2.split.json --manifest ml/data/manifests/nandi_synthetic_phase2.json
& $py -m ml.scripts.audit_collections --collections ml/configs/phase2_collections.json --output ml/data/evaluation/phase2_cross_source_audit.json
& $py -m ml.scripts.readiness_matrix --collections ml/configs/phase2_collections.json --output ml/reports/PHASE2_LABEL_MATRIX.json
& $py -m pytest -q ml/tests
```

The synthetic split is generated once and the existing verified split is reused for validation. All generated labels have explicit synthetic provenance. `configs/phase2_collections.json` keeps NYC real operational records and Nandi generated narratives in separate collections. The cross-collection audit checks exact, near-duplicate and repeated-template groups but cannot prove that all multilingual paraphrases are independent.

See [Phase 2 training proposal](reports/PHASE2_TRAINING_PROPOSAL.md), [source decisions](reports/SOURCE_AUDIT.md), and [Nandi provenance](reports/NANDI_PHASE2.md). Mendeley acquisition remains blocked for the documented rights/privacy reasons; OpenCity's normal CSV route is covered below.

## Track A Phase 3: real Bengaluru complaint candidates

The official [OpenCity/Janaagraha complaint-log resource](https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f) offered a normal CSV browser download separate from the previously blocked DataStore API. An already-present publisher CSV matched the official MD5, then was streamed into a 1,000-row minimized/redacted local extract. The full CSV with addresses and coordinates was deleted after verification. The retained text files are Git-ignored and have restricted Windows ACLs. All 1,000 rows remain **pending human privacy and label review**; do not train or publish from them yet.

From the repository root, verify the retained collection without downloading anything:

```powershell
$py = 'backend\venv\Scripts\python.exe'
& $py -m ml.scripts.validate --processed ml/data/processed/opencity_ichangemycity_2019_2022_phase3.jsonl --split ml/data/evaluation/opencity_ichangemycity_2019_2022_phase3.split.json --manifest ml/data/manifests/opencity_ichangemycity_2019_2022_phase3.json
& $py -m ml.scripts.audit_collections --collections ml/configs/phase3_collections.json --output ml/data/evaluation/phase3_cross_source_audit.json
& $py -m ml.scripts.readiness_matrix --collections ml/configs/phase3_collections.json --output ml/reports/PHASE3_LABEL_MATRIX.json
& $py -m pytest -q ml/tests
```

To reproduce the extract in a clean workspace, obtain the normal CSV from the **official resource page** only if openly offered, verify its publisher MD5 `7cf55ab5a16658abd83f372b5c26851d`, place it briefly under ignored `ml/data/raw/opencity_unreviewed/`, and run `ml.scripts.minimize_opencity` with the source resource URL and `CC BY-SA 2.0` license string. The exact source SHA-256, output checksums, sampling rule, count and retention record are in the ignored Phase 3 manifest and [collection summary](reports/COLLECTION_SUMMARY.md). Do not use a third-party mirror to work around access failure. The full CSV includes personal location fields and should be removed after the minimized output is checked.

Review only the redacted local records referenced by `ml/data/evaluation/opencity_ichangemycity_2019_2022_phase3.stratified_review.json`. That file contains hashed IDs and labels, no narratives. See [privacy protocol](reports/PHASE3_PRIVACY_PROTOCOL.md), [official source evidence](reports/OPENCITY_PHASE3.md), and [suitability report](reports/REAL_TEXT_SUITABILITY_PHASE3.md).

## Track A Phase 4: local human review

The refreshed 30-ID queue is an initial audit and covers all three frozen splits and every observed privacy-flag type. **No human decisions have been entered and none of the 1,000 records is cleared.** The retained OpenCity text stays under ignored `ml/data/`; do not copy it to Git, screenshots, tickets, cloud tools or an external LLM. The review tool is a local command-line program and opens no network listener.

After the project owner names two independent reviewers and a distinct adjudicator and approves local access/retention, initialize the store once from the repository root. Choose actual identity codes and enter unique passphrases at the prompts, not in shell history:

```powershell
backend\venv\Scripts\python.exe -m ml.scripts.review_local init --reviewer-a ReviewerA --reviewer-b ReviewerB --adjudicator Adjudicator
```

The coordinator gives each authorized person a hashed ID from the ignored queue. A reviewer then runs `show --reviewer ReviewerA --record-id <64-hex-ID>` and `review --reviewer ReviewerA --record-id <64-hex-ID>`; the second reviewer uses their own identity. The adjudicator runs `adjudicate --adjudicator Adjudicator --record-id <64-hex-ID>` only after both submissions. Commands use the same `backend\venv\Scripts\python.exe -m ml.scripts.review_local` prefix. `status --actor ReviewerA --record-id <64-hex-ID>` reveals only progress before adjudication. An adjudicator may create a protected, write-once evidence snapshot with `export --adjudicator Adjudicator --output ml/data/reviews/evidence-YYYYMMDD.json`; never put that snapshot in Git.

See the [full operating instructions and rubric](reports/REVIEW_LOCAL_PHASE4.md), [privacy and rights audit](reports/PRIVACY_RIGHTS_PHASE4.md), [source-category pilot](reports/SOURCE_CATEGORY_PILOT_PHASE4.md) and [training-readiness gate](reports/PHASE4_REVIEW_GATE.md). The review store is not initialized until real reviewers and access controls are assigned; no fictional submissions are created.

## Track A Phase 5: offline review acceleration

`backend\venv\Scripts\python.exe -m ml.scripts.phase5_screen` checks the frozen Phase 4 hashes, then creates or verifies a restricted, Git-ignored machine-screening artifact and a prioritized 1,000-ID review plan. It prints only aggregate counts; it makes no network requests, trains no model and does not create human decisions. The existing review CLI can show unverified machine evidence codes and the authenticated reviewer's own progress. See the [screening summary](reports/PHASE5_AUTOMATED_SCREENING.md), [human review plan](reports/PHASE5_HUMAN_REVIEW_PLAN.md), and [validation](reports/PHASE5_VALIDATION.md). **All 1,000 records remain uncleared.**
