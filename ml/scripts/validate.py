"""Check prepared JSONL schema, remaining obvious PII and split integrity."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ml.scripts.preprocess import EMAIL, PHONE, US_PHONE, IDENTIFIER, ADDRESS, FIELDS, file_digest
from ml.scripts.split import canonical, group_records

OPTIONAL_FIELDS = {"data_kind", "urgency_source", "source_domain", "complaint_label", "label_source", "source_subcategory", "source_agency", "source_category_raw", "privacy_flags", "privacy_status"}


def validate(processed: Path, split_path: Path, manifest_path: Path | None = None) -> dict:
    with processed.open(encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    issues = []
    ids = set()
    labels: Counter = Counter()
    for position, row in enumerate(records, 1):
        if not set(FIELDS).issubset(row) or set(row) - set(FIELDS) - OPTIONAL_FIELDS:
            issues.append(f"row {position}: schema mismatch")
        record_id = row.get("record_id")
        if not record_id or record_id in ids:
            issues.append(f"row {position}: missing or duplicate ID")
        if record_id:
            ids.add(record_id)
        text = row.get("complaint_text", "")
        if not isinstance(text, str) or not canonical(text):
            issues.append(f"row {position}: empty text")
        elif any(pattern.search(text) for pattern in (EMAIL, PHONE, US_PHONE, IDENTIFIER, ADDRESS)):
            issues.append(f"row {position}: obvious personal identifier remains")
        if not row.get("privacy_review_required"):
            issues.append(f"row {position}: privacy review flag missing")
        if row.get("category"):
            labels[row["category"]] += 1
            if row.get("category_source") not in ("source_provided", "synthetic_generated", "human_reviewed"):
                issues.append(f"row {position}: unlabeled category provenance")
        elif row.get("category_source"):
            issues.append(f"row {position}: category provenance without label")
        if row.get("data_kind") == "synthetic":
            if row.get("category") and row.get("category_source") != "synthetic_generated":
                issues.append(f"row {position}: synthetic category provenance mismatch")
            if row.get("urgency") and row.get("urgency_source") != "synthetic_generated":
                issues.append(f"row {position}: synthetic urgency provenance mismatch")
        elif row.get("category_source") == "synthetic_generated":
            issues.append(f"row {position}: synthetic label on an unmarked record")
        if row.get("complaint_label") and not row.get("label_source"):
            issues.append(f"row {position}: complaint detection label lacks provenance")
        if row.get("data_kind") == "real" and row.get("text_kind") == "narrative" and row.get("privacy_status") not in ("pending_human_review", "reviewed_approved"):
            issues.append(f"row {position}: real narrative lacks privacy status")
        if row.get("privacy_status") == "reviewed_approved" and row.get("privacy_review_required"):
            issues.append(f"row {position}: contradictory privacy review state")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    memberships = {name: set(split["splits"][name]) for name in ("train", "validation", "test")}
    if set.union(*memberships.values()) != ids:
        issues.append("split coverage mismatch")
    if any(memberships[a] & memberships[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        issues.append("record appears in multiple splits")
    assignment = {item: name for name, members in memberships.items() for item in members}
    if all(isinstance(row.get("complaint_text"), str) and row.get("record_id") for row in records):
        for group in group_records(records, bool(split.get("template_aware"))):
            if len({assignment.get(records[i]["record_id"]) for i in group}) != 1:
                issues.append("near-duplicate group crosses splits")
                break
    if manifest_path:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checksum = manifest.get("output_sha256") or manifest.get("processed_sha256")
        expected_count = manifest.get("counts", {}).get("output", manifest.get("row_count"))
        if checksum != file_digest(processed):
            issues.append("processed checksum mismatch")
        if expected_count != len(records):
            issues.append("processed row-count mismatch")
        if manifest.get("source_id") != (records[0].get("source_id") if records else manifest.get("source_id")):
            issues.append("processed source mismatch")
    return {"ok": not issues, "issues": issues, "records": len(records), "sources": sorted({row["source_id"] for row in records}), "category_distribution": dict(labels), "split_counts": {name: len(members) for name, members in memberships.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    result = validate(args.processed, args.split, args.manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
