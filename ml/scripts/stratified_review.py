"""Select only hashed IDs and non-sensitive metadata for local human review."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def choose(records: list[dict], split: dict, count: int = 30) -> dict:
    if count < 3:
        raise ValueError("Review sample must contain at least three records")
    assignment = {record_id: name for name, members in split["splits"].items() for record_id in members}
    if set(assignment) != {row["record_id"] for row in records}:
        raise ValueError("Split does not cover exactly the processed records")
    categories = Counter(row.get("category") or "unlabeled" for row in records)
    def order(row: dict):
        return hashlib.sha256(("track-a-review-v1\0" + row["record_id"]).encode()).hexdigest()
    selected = {}
    # Cover each split and the main privacy flag groups before filling rare categories.
    for split_name in ("train", "validation", "test"):
        members = [row for row in records if assignment[row["record_id"]] == split_name]
        for predicate in (lambda row: bool(row.get("privacy_flags")), lambda row: not row.get("privacy_flags")):
            candidates = sorted((row for row in members if predicate(row)), key=order)
            if candidates and len(selected) < count:
                selected[candidates[0]["record_id"]] = candidates[0]
    flag_counts = Counter(flag for row in records for flag in row.get("privacy_flags", []))
    for flag in sorted(flag_counts, key=lambda name: (flag_counts[name], name)):
        candidates = sorted((row for row in records if flag in row.get("privacy_flags", [])), key=order)
        if candidates and len(selected) < count:
            selected.setdefault(candidates[0]["record_id"], candidates[0])
    for category in sorted(categories, key=lambda label: (categories[label], label)):
        candidates = sorted((row for row in records if (row.get("category") or "unlabeled") == category), key=order)
        if len(selected) >= count:
            break
        if candidates:
            selected.setdefault(candidates[0]["record_id"], candidates[0])
    for row in sorted(records, key=order):
        if len(selected) >= count:
            break
        selected.setdefault(row["record_id"], row)
    items = [{"record_id": row["record_id"], "source_category": row.get("category"), "script_hint": row.get("language"), "split": assignment[row["record_id"]], "privacy_flags": row.get("privacy_flags", [])} for row in selected.values()]
    return {"version": 2, "review_status": "pending", "items": sorted(items, key=lambda item: item["record_id"]), "counts": {"selected": len(items), "by_split": dict(Counter(item["split"] for item in items)), "categories_covered": len({item["source_category"] for item in items}), "flagged": sum(bool(item["privacy_flags"]) for item in items), "risk_types_covered": sorted({flag for item in items for flag in item["privacy_flags"]})}, "questions": ["Is this genuine citizen-authored complaint text rather than a descriptor or staff remark?", "Are direct or indirect identifiers still present after automated redaction?", "Is the original source category correct for this narrative?", "What is the human-verified language or code mix?", "Is this related to another complaint or a repeated template?", "Should this case be excluded from any public or model use?"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Review queue already exists")
    records = [json.loads(line) for line in args.processed.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = choose(records, json.loads(args.split.read_text(encoding="utf-8")), args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
