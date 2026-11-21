# Validation evidence

Executed on Windows in the repository workspace on 2026-11-20.

| Check | Result |
| --- | --- |
| `backend\venv\Scripts\python.exe -m pytest -q ml/tests` from repository root | 11 passed |
| `venv\Scripts\python.exe -m pytest -q` from `backend/` | 63 passed, one upstream Starlette deprecation warning |
| `python -m ml.scripts.validate` against prepared NYC sample, split and manifest | Passed; 1,000 records, full split coverage, no duplicate group crossing, checksum matched |
| Repeated `python -m ml.scripts.acquire --source nyc_311_2024_bounded` | Existing verified file reused; no second download |
| Reprocessed the same raw file to a temporary output | Byte-for-byte SHA-256 match with prepared JSONL |
| `git check-ignore` on raw JSON file | Confirmed `ml/data/` exclusion |

An initial combined ML/backend pytest call from the repository root failed during backend collection because `app` was not on Python's module path. The backend suite passed when rerun from its intended `backend/` working directory, as shown above. No application code or production service was modified for this data task.

The validator is a structural/privacy-pattern gate, not a human privacy, source-label, or model-quality audit. No browser test or frontend build was needed because the task made no application changes.

## Phase 2 evidence

Executed 2026-11-20 on the same Windows workspace:

| Check | Result |
| --- | --- |
| `backend\venv\Scripts\python.exe -m pytest -q ml/tests` from repository root | 21 passed, including original 11 and new source/split/leakage/readiness checks |
| `venv\Scripts\python.exe -m pytest -q` from `backend/` | 63 passed; one upstream Starlette deprecation warning |
| `ml.scripts.validate` with Nandi processed file, template-aware split and acquisition manifest | Passed; 150 records, checksum/count/source matched |
| `ml.scripts.audit_collections` over NYC + Nandi | Passed; 0 detected cross-source related groups, 0 cross-split related groups |
| `ml.scripts.readiness_matrix` | 0 real narratives, 1,000 real operational rows, 150 synthetic rows; 0 independent real complaint-detection labels |
| Nandi repeat acquisition | Reused verified raw and prepared checksums without network access |

No app or production database changes were part of Phase 2. The synthetic split and cross-collection audit are automated leakage guards, not a reviewed independent evaluation set.

## Track A Phase 3 evidence

Executed 2026-11-20 in the same Windows workspace:

| Check | Result |
| --- | --- |
| `backend\venv\Scripts\python.exe -m pytest -q ml/tests` from repository root | **26 passed**, including prior acquisition, privacy, provenance, split and matrix tests |
| `venv\Scripts\python.exe -m pytest -q` from `backend/` | **63 passed**, one upstream Starlette deprecation warning |
| OpenCity processed-file validator with source manifest and grouped split | **Passed**, 1,000 rows, matching SHA-256/count/source, no recognized direct identifier left in processed text |
| Cross-collection audit over NYC, Nandi and OpenCity | **Passed**, 0 detected related groups crossing sources or split boundaries |
| Publisher provenance | 16,071 parsed CSV rows; 17 expected columns; local MD5 matched published `7cf55ab5a16658abd83f372b5c26851d`; SHA-256 recorded |
| Privacy minimization | Full CSV with address/coordinate columns removed after minimized and processed checksums matched; retained text files have explicit restricted Windows ACLs and are ignored by Git |
| Local human-review queue | 30 hashed IDs, 29 original categories, all three splits, 11 flagged records; no narrative text in queue |

The validator and regex redactor cannot prove that every identifier was removed. **Human privacy review completed: 0 records.** The 676/157/167 split is a leakage-checked research split, not an independently reviewed real evaluation benchmark. No model training, frontend change, production database use or deployment took place.

## Track A Phase 4 evidence

Executed 2026-11-20 on the same Windows workspace:

| Check | Result |
| --- | --- |
| `backend\venv\Scripts\python.exe -m pytest -q ml/tests` | **40 passed** after final review access and export changes |
| `venv\Scripts\python.exe -m pytest -q` from `backend/` | 63 passed, one upstream Starlette deprecation warning |
| OpenCity processed-file validator with refreshed manifest and frozen split | Passed, 1,000 rows, no structural issues |
| NYC + Nandi + OpenCity cross-collection audit after redaction hardening | Passed, 0 cross-source and 0 cross-split related groups |
| Aggregate privacy-pattern scanner | 0 matches in ten direct-pattern classes across retained minimized and processed OpenCity text; human privacy clearance remains 0 |
| Refreshed queue | 30 hashed IDs; 21/5/4 train/validation/test, 25 source categories, 13 flagged IDs, all observed flag types |
| Git and Windows ACL checks | Retained real text and queue ignored by Git; explicit restricted ACLs on both text files |

All review-interface submissions in automated tests use synthetic fixtures. No real decision store was initialized and no production service or model was changed. See the [Phase 4 gate report](PHASE4_REVIEW_GATE.md) for SHA-256 values and remaining approvals.
