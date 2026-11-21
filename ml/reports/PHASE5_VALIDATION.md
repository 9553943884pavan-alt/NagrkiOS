# Phase 5 validation evidence

Executed locally on Windows on 2026-11-20. No real narrative text was printed, sent to an external model, inserted into the live app or added to Git. No review database or human decision was created.

| Check | Result |
| --- | --- |
| Frozen Phase 4 processed/manifest/split/queue hashes | Matched before screening; source files unchanged |
| Local deterministic screening | 1,000/1,000 records; versioned checksum-bound output; cached rerun accepted |
| Protected review plan | 1,000 unique IDs, mutually exclusive batches, all frozen split members; Git-ignored |
| `python -m ml.scripts.phase5_audit` | Passed: frozen hashes and plan coverage, zero narrative fields or human decisions in machine artifacts, zero training eligibility |
| Windows ACLs | Phase 5 directory, screening file and plan explicitly allow only owner, sandbox account, SYSTEM and administrators; inheritance removed |
| Cross-split candidate duplicate check | 0 candidates at current exact/template/high-token-overlap thresholds; semantic or translated matches remain possible |
| Human decision store | Absent; 0 approvals, 0 exclusions, 0 training-eligible |
| `backend\venv\Scripts\python.exe -m pytest -q ml/tests` | **49 passed** after review-screening integration test |
| `venv\Scripts\python.exe -m pytest -q` from `backend/` | **63 passed**, one upstream Starlette deprecation warning |

The initial execution caught a Windows ACL helper defect: the environment variable named the workspace owner while the process ran under a distinct sandbox identity. The helper now grants the actual process account plus the owner. The newly created Phase 5 directory permissions were repaired and the screen rerun successfully. This was a local research-output permission issue; no source data or backend application changed.

Machine screening is a prioritization tool, not a verified annotation or evidence of consent. Static keyword and script cues have unmeasured false-positive and false-negative rates, and no genuine held-out labeled set was used to score them. The prior Phase 4 privacy redaction and grouped-split validator remain required.

Three specialized Codex subagents were started for privacy, quality and reviewer workflow, but each encountered a usage-limit error before producing changes. The lead agent completed those roles sequentially and ran the separate structural-audit command. A genuinely independent human quality audit remains pending; the structural check cannot assess narrative-level false negatives or rights.
