"""Count task labels by dataset kind, category and language without sharing text."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def summarize(collections: list[dict]) -> dict:
    source_counts = {}
    genuine = defaultdict(Counter)
    candidate = defaultdict(Counter)
    synthetic = defaultdict(Counter)
    detection = Counter()
    available_languages = defaultdict(Counter)
    synthetic_domain_none = 0
    synthetic_domain_labeled = 0
    usable_real = 0
    for entry in collections:
        source_id, kind = entry["source_id"], entry["kind"]
        with Path(entry["processed"]).open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        source_counts[source_id] = len(rows)
        for row in rows:
            if row.get("source_id") != source_id:
                raise ValueError("Source mismatch in processed collection")
            language = row.get("language") or "unknown"
            available_languages[source_id][language] += 1
            category = row.get("category")
            if kind == "synthetic":
                if row.get("data_kind") != "synthetic":
                    raise ValueError("Synthetic collection lacks explicit marker")
                if row.get("source_domain") == "none":
                    synthetic_domain_none += 1
                elif row.get("source_domain"):
                    synthetic_domain_labeled += 1
                if category and row.get("category_source") == "synthetic_generated":
                    synthetic[category][language] += 1
            elif kind == "real_narrative":
                if row.get("data_kind") == "synthetic" or row.get("text_kind") != "narrative":
                    raise ValueError("Real-narrative collection misclassified")
                if category and row.get("category_source") in ("source_provided", "human_reviewed"):
                    candidate[category][language] += 1
                    if row.get("privacy_status") == "reviewed_approved" and row.get("privacy_review_required") is False:
                        genuine[category][language] += 1
                if row.get("privacy_status") == "reviewed_approved" and row.get("privacy_review_required") is False:
                    usable_real += 1
                    if row.get("complaint_label") is not None and row.get("label_source") in ("dataset_annotation", "human_reviewed"):
                        detection[row["complaint_label"]] += 1
            elif kind != "real_operational":
                raise ValueError("Unknown collection kind")
    return {
        "source_counts": source_counts,
        "real_narrative_records": sum(source_counts[entry["source_id"]] for entry in collections if entry["kind"] == "real_narrative"),
        "usable_privacy_reviewed_real_narratives": usable_real,
        "real_operational_records": sum(source_counts[entry["source_id"]] for entry in collections if entry["kind"] == "real_operational"),
        "synthetic_records": sum(source_counts[entry["source_id"]] for entry in collections if entry["kind"] == "synthetic"),
        "synthetic_complaint_domain_records": synthetic_domain_labeled,
        "synthetic_domain_none_records": synthetic_domain_none,
        "independent_detection_labels": dict(detection),
        "genuine_category_by_language": {category: dict(languages) for category, languages in sorted(genuine.items())},
        "candidate_source_category_by_script_or_language": {category: dict(languages) for category, languages in sorted(candidate.items())},
        "synthetic_category_by_language": {category: dict(languages) for category, languages in sorted(synthetic.items())},
        "source_language_distribution": {source: dict(languages) for source, languages in sorted(available_languages.items())},
        "policy": "Synthetic labels are generated. Real source categories are counted as usable only after explicit human privacy approval; unreviewed narratives remain candidates. Script hints are not verified languages. Operational descriptors never count as complaint text."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(json.loads(args.collections.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("source_counts", "real_narrative_records", "real_operational_records", "synthetic_records", "independent_detection_labels")}))


if __name__ == "__main__":
    main()
