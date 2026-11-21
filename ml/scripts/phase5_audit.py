"""Independent structural audit of local Phase 5 metadata; emits counts only."""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

from ml.scripts.phase5_screen import DATA, EXPECTED, MANIFEST, OUTPUT, PLAN, PROCESSED, QUEUE, SPLIT, _read_jsonl
from ml.scripts.preprocess import file_digest

FORBIDDEN = {"complaint_text", "redacted_text", "description", "title", "password", "passphrase", "api_key"}


def audit(screening: Path = OUTPUT, plan: Path = PLAN) -> dict:
    screening, plan = Path(screening), Path(plan)
    if not screening.resolve().is_relative_to(DATA.resolve()) or not plan.resolve().is_relative_to(DATA.resolve()):
        raise ValueError("Protected artifacts must stay under ml/data")
    expected_paths = {"processed": PROCESSED, "split": SPLIT, "queue": QUEUE, "manifest": MANIFEST}
    if any(file_digest(path) != EXPECTED[name] for name, path in expected_paths.items()):
        raise ValueError("Frozen Phase 4 input changed")
    metadata = json.loads(screening.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if metadata.get("output_sha256") != file_digest(screening) or metadata.get("input_sha256", {}).get("processed") != EXPECTED["processed"]:
        raise ValueError("Machine screening manifest mismatch")
    records = _read_jsonl(screening)
    source_ids = {row["record_id"] for row in _read_jsonl(PROCESSED)}
    if len(records) != 1000 or len(source_ids) != 1000 or {row["record_id"] for row in records} != source_ids:
        raise ValueError("Machine assessments do not cover exactly the source IDs")
    if any(FORBIDDEN & set(row) or any(key.startswith("human_") for key in row)
           or row.get("training_eligibility") is not False for row in records):
        raise ValueError("Screening contains text, human decisions or eligibility")
    review_plan = json.loads(plan.read_text(encoding="utf-8"))
    items = review_plan["items"]
    if (len(items) != 1000 or {item["record_id"] for item in items} != source_ids
            or review_plan["screening_sha256"] != file_digest(screening)
            or review_plan["processed_sha256"] != EXPECTED["processed"]
            or review_plan["split_sha256"] != EXPECTED["split"]):
        raise ValueError("Review plan is incomplete or stale")
    if any(FORBIDDEN & set(item) or any(key.startswith("human_") for key in item) for item in items):
        raise ValueError("Review plan contains sensitive text or human decisions")
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    assignment = {record_id: name for name, members in split["splits"].items() for record_id in members}
    if any(item["split"] != assignment[item["record_id"]] for item in items):
        raise ValueError("Review plan changed frozen split membership")
    queue_ids = {item["record_id"] for item in json.loads(QUEUE.read_text(encoding="utf-8"))["items"]}
    if len(queue_ids) != 30 or not queue_ids <= source_ids:
        raise ValueError("Phase 4 queue does not match source")
    ignored = subprocess.run(["git", "check-ignore", str(screening), str(plan)], capture_output=True, text=True)
    if ignored.returncode != 0 or len(ignored.stdout.splitlines()) != 2:
        raise ValueError("Phase 5 artifacts are not Git-ignored")
    return {"screened": len(records), "planned": len(items), "phase4_audit_ids": len(queue_ids),
            "batches": dict(Counter(item["review_batch"] for item in items)),
            "human_decisions_in_machine_artifact": 0,
            "training_eligible": sum(item["training_eligibility"] for item in records),
            "screening_sha256": file_digest(screening), "plan_sha256": file_digest(plan)}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
