"""Produce aggregate-only data quality metrics; never emit source text."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from ml.scripts.split import canonical, group_records


def profile(records: list[dict], split: dict) -> dict:
    missing = Counter()
    languages = Counter()
    labels = Counter()
    kinds = Counter()
    statuses = Counter()
    exact = Counter()
    labels_by_text = defaultdict(set)
    parent_by_subcategory = defaultdict(set)
    malformed_dates = 0
    observed_hours = []
    for row in records:
        for field in ("complaint_text", "language", "category", "department", "urgency", "location", "created_at", "closed_at", "status"):
            if row.get(field) is None or row.get(field) == "":
                missing[field] += 1
        languages[row.get("language") or "unknown"] += 1
        labels[row.get("category") or "unlabeled"] += 1
        kinds[row.get("text_kind") or "unknown"] += 1
        statuses[row.get("status") or "unknown"] += 1
        exact[canonical(row.get("complaint_text") or "")] += 1
        if row.get("category"):
            labels_by_text[canonical(row.get("complaint_text") or "")].add(row["category"])
            if row.get("source_subcategory"):
                parent_by_subcategory[row["source_subcategory"]].add(row["category"])
        if row.get("created_at") and row.get("closed_at"):
            try:
                start = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(row["closed_at"].replace("Z", "+00:00"))
                hours = (end - start).total_seconds() / 3600
                if hours >= 0:
                    observed_hours.append(hours)
                else:
                    malformed_dates += 1
            except (TypeError, ValueError):
                malformed_dates += 1
    groups = group_records(records, bool(split.get("template_aware")))
    observed_hours.sort()
    notes = ["These aggregate metrics disclose no complaint text.", "Language fields may be source-provided or script-inferred; neither is independently verified here.", "Observed closure intervals require censoring and case-definition review before ETA research."]
    if kinds.get("descriptor_label"):
        notes.append("Descriptor labels are not citizen complaint narratives or valid model features.")
    if kinds.get("synthetic_narrative"):
        notes.append("Synthetic narratives and generated labels are not independent real-world ground truth.")
    return {
        "records": len(records),
        "source_ids": sorted({row["source_id"] for row in records}),
        "missing_by_field": dict(missing),
        "language_hints": dict(languages),
        "text_kinds": dict(kinds),
        "category_distribution": dict(labels),
        "status_distribution": dict(statuses),
        "distinct_texts": len(exact),
        "exact_duplicate_rows": sum(count - 1 for count in exact.values()),
        "exact_text_with_conflicting_category_groups": sum(len(categories) > 1 for categories in labels_by_text.values()),
        "subcategories_under_multiple_categories": sum(len(categories) > 1 for categories in parent_by_subcategory.values()),
        "related_groups": len(groups),
        "related_rows_beyond_group_representatives": len(records) - len(groups),
        "negative_or_malformed_closure_dates": malformed_dates,
        "valid_closure_pairs": len(observed_hours),
        "median_observed_closure_hours": median(observed_hours) if observed_hours else None,
        "split_counts": split["counts"],
        "privacy_review_required_count": sum(bool(row.get("privacy_review_required")) for row in records),
        "notes": notes
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.processed.read_text(encoding="utf-8").splitlines() if line.strip()]
    split = json.loads(args.split.read_text(encoding="utf-8"))
    result = profile(records, split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "records": result["records"]}))


if __name__ == "__main__":
    main()
