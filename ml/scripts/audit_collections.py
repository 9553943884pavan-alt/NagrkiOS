"""Audit separation and related-text leakage across prepared collections.

Only hashed record IDs and aggregate counts leave this script; no case text is printed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ml.scripts.split import group_records


def audit(collections: list[dict]) -> dict:
    if len({entry["source_id"] for entry in collections}) != len(collections):
        raise ValueError("Each source must have one separate collection")
    if len({str(Path(entry["processed"]).resolve()) for entry in collections}) != len(collections):
        raise ValueError("Collections must use separate processed files")
    rows: list[dict] = []
    source_by_id = {}
    splits_by_id = {}
    issues = []
    for entry in collections:
        source_id = entry["source_id"]
        kind = entry["kind"]
        if kind not in ("real_narrative", "real_operational", "synthetic"):
            raise ValueError("Unknown collection kind")
        with Path(entry["processed"]).open(encoding="utf-8") as stream:
            current = [json.loads(line) for line in stream if line.strip()]
        split = json.loads(Path(entry["split"]).read_text(encoding="utf-8"))
        allocation = {record_id: name for name, members in split["splits"].items() for record_id in members}
        if set(allocation) != {row["record_id"] for row in current}:
            issues.append(f"{source_id}: split coverage mismatch")
        for row in current:
            record_id = row["record_id"]
            if row.get("source_id") != source_id:
                issues.append(f"{source_id}: row source mismatch")
            if record_id in source_by_id:
                issues.append("duplicate record ID across collections")
            if kind == "synthetic":
                if row.get("data_kind") != "synthetic":
                    issues.append(f"{source_id}: missing explicit synthetic marker")
                if row.get("category") and row.get("category_source") not in ("synthetic_generated", "synthetic_source_provided"):
                    issues.append(f"{source_id}: generated category provenance missing")
                if row.get("urgency") and row.get("urgency_source") != "synthetic_generated":
                    issues.append(f"{source_id}: synthetic urgency provenance missing")
            elif row.get("data_kind") == "synthetic":
                issues.append(f"{source_id}: synthetic row in real collection")
            if kind == "real_narrative" and row.get("privacy_status") not in ("pending_human_review", "reviewed_approved"):
                issues.append(f"{source_id}: missing real-narrative privacy state")
            if kind == "real_operational" and row.get("text_kind") == "narrative":
                issues.append(f"{source_id}: operational descriptor marked narrative")
            source_by_id[record_id] = source_id
            splits_by_id[record_id] = allocation.get(record_id)
        rows.extend(current)
    related_groups = group_records(rows, template_mode=True)
    cross_source = []
    cross_split = []
    quarantine_ids = set()
    for group in related_groups:
        members = [rows[index]["record_id"] for index in group]
        sources = {source_by_id[record_id] for record_id in members}
        allocations = {splits_by_id[record_id] for record_id in members}
        if len(sources) > 1:
            cross_source.append(group)
            quarantine_ids.update(members)
        if len(allocations) > 1:
            cross_split.append(group)
            quarantine_ids.update(members)
    if cross_split:
        issues.append("related records cross split boundaries")
    if cross_source:
        issues.append("related records occur in multiple sources; quarantine before cross-source evaluation")
    return {"ok": not issues, "issues": sorted(set(issues)), "collection_counts": {entry["source_id"]: sum(row["source_id"] == entry["source_id"] for row in rows) for entry in collections}, "cross_source_related_groups": len(cross_source), "cross_split_related_groups": len(cross_split), "quarantined_record_ids": sorted(quarantine_ids), "method": "exact, >=0.90 character similarity, or repeated-template trigram similarity; manual review still required"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collections", type=Path, required=True, help="Local JSON list of source_id, kind, processed, split paths")
    parser.add_argument("--output", type=Path, required=True, help="Ignored local report containing hashed quarantine IDs")
    args = parser.parse_args()
    entries = json.loads(args.collections.read_text(encoding="utf-8"))
    result = audit(entries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("ok", "issues", "collection_counts", "cross_source_related_groups", "cross_split_related_groups")}))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
