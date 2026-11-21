"""Make a bounded, redacted OpenCity research extract from a verified local CSV.

No network access. The publisher CSV must be verified separately before calling this.
No case text is printed or committed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ml.scripts.preprocess import file_digest, language_hint, normalize, redact

SOURCE_ID = "opencity_ichangemycity_2019_2022"
EXPECTED = {"title", "description", "category_title", "sub_category_title", "civic_agency_title", "created_at", "complaint_status_title"}
COORD = re.compile(r"(?<!\d)\d{1,2}\.\d{4,}\s*,\s*\d{1,3}\.\d{4,}(?!\d)")
HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,30}\b")
INDIRECT = re.compile(r"\b(?:ward|village|house|flat|apartment|near|opposite|behind|beside|landmark)\b|(?:\u0917\u093e\u0901\u0935|\u0917\u093e\u0902\u0935|\u0935\u093e\u0930\u094d\u0921|\u092e\u0915\u093e\u0928)", re.I)
MIN_NARRATIVE_WORDS = 5


def private_text(value: str) -> tuple[str, list[str]]:
    cleaned = normalize(value)
    flags = []
    if COORD.search(cleaned):
        cleaned = COORD.sub("[COORDINATES]", cleaned)
        flags.append("coordinates")
    if HANDLE.search(cleaned):
        cleaned = HANDLE.sub("[HANDLE]", cleaned)
        flags.append("handle")
    cleaned, general = redact(cleaned)
    flags.extend(general)
    if INDIRECT.search(cleaned):
        flags.append("possible_location")
    return cleaned, sorted(set(flags))


def detect_encoding(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open("r", encoding=encoding) as stream:
                for _ in iter(lambda: stream.read(1024 * 1024), ""):
                    pass
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("Publisher CSV encoding is unsupported; do not replace invalid characters")


def read_rows(path: Path, encoding: str):
    with path.open("r", encoding=encoding, newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not EXPECTED.issubset(reader.fieldnames):
            raise ValueError("Publisher CSV lacks required title/description/category metadata")
        for position, row in enumerate(reader, 1):
            if None in row:
                raise ValueError(f"Malformed CSV row {position}")
            yield position, row


def selected_indices(path: Path, max_rows: int, encoding: str) -> tuple[list[int], dict]:
    if max_rows < 1 or max_rows > 2000:
        raise ValueError("Bounded sample size must be between 1 and 2,000")
    eligible = []
    total = 0
    for position, row in read_rows(path, encoding):
        total += 1
        description = normalize(row.get("description") or "")
        if (row.get("category_title") or "").strip() and len(description) >= 25 and len(re.findall(r"\w+", description, flags=re.UNICODE)) >= MIN_NARRATIVE_WORDS:
            eligible.append(position)
    if not eligible:
        raise ValueError("No rows with narrative description and original category")
    target = min(max_rows, len(eligible))
    if target == 1:
        chosen = [eligible[len(eligible) // 2]]
    else:
        chosen = sorted({eligible[round(index * (len(eligible) - 1) / (target - 1))] for index in range(target)})
    return chosen, {"publisher_rows": total, "eligible_description_category_rows": len(eligible), "selected_rows": len(chosen), "minimum_narrative_words": MIN_NARRATIVE_WORDS, "minimum_narrative_characters": 25, "sample_method": "systematic positions over rows with narrative-length description and source category"}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def minimize(full_csv: Path, data_root: Path, *, source_url: str, license_name: str, max_rows: int = 1000) -> dict:
    if not source_url.startswith("https://data.opencity.in/") or not license_name.startswith("CC BY-SA 2.0"):
        raise ValueError("Official OpenCity provenance and license must be verified first")
    if full_csv.stat().st_size > 100_000_000:
        raise ValueError("Unexpectedly large publisher export")
    full_hash = file_digest(full_csv)
    manifest_path = data_root / "manifests" / f"{SOURCE_ID}_phase3.json"
    minimal_path = data_root / "raw" / SOURCE_ID / "field_minimized_redacted.jsonl"
    prepared_path = data_root / "processed" / f"{SOURCE_ID}_phase3.jsonl"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("publisher_csv_sha256") == full_hash and minimal_path.exists() and prepared_path.exists()
                and file_digest(minimal_path) == manifest.get("minimal_sha256")
                and file_digest(prepared_path) == manifest.get("processed_sha256")):
            return manifest
        raise ValueError("Existing extract or manifest differs; inspect before continuing")
    if minimal_path.exists() or prepared_path.exists():
        raise FileExistsError("Unmanifested extract exists; inspect before continuing")
    encoding = detect_encoding(full_csv)
    indices, metrics = selected_indices(full_csv, max_rows, encoding)
    metrics["decoded_encoding"] = encoding
    chosen = set(indices)
    minimal_rows = []
    prepared_rows = []
    flags_count: Counter = Counter()
    label_counts: Counter = Counter()
    language_counts: Counter = Counter()
    for position, source in read_rows(full_csv, encoding):
        if position not in chosen:
            continue
        record_id = hashlib.sha256(f"{SOURCE_ID}\0{full_hash}\0{position}".encode()).hexdigest()
        title, title_flags = private_text(source.get("title") or "")
        description, description_flags = private_text(source["description"])
        label = normalize(source["category_title"])
        flags = sorted(set(title_flags + description_flags))
        flags_count.update(flags)
        label_counts[label] += 1
        language = language_hint(description)
        language_counts[language or "unknown"] += 1
        minimal_rows.append({
            "record_id": record_id, "title": title, "description": description,
            "category_title": label,
            "sub_category_title": normalize(source.get("sub_category_title") or "") or None,
            "civic_agency_title": normalize(source.get("civic_agency_title") or "") or None,
            "created_at": normalize(source.get("created_at") or "") or None,
            "complaint_status_title": normalize(source.get("complaint_status_title") or "") or None,
        })
        prepared_rows.append({
            "record_id": record_id, "source_id": SOURCE_ID, "data_kind": "real",
            "complaint_text": description, "text_kind": "narrative", "language": language,
            "category": label, "category_source": "source_provided",
            "source_subcategory": normalize(source.get("sub_category_title") or "") or None,
            "source_agency": normalize(source.get("civic_agency_title") or "") or None,
            "department": None, "urgency": None, "location": None,
            "created_at": normalize(source.get("created_at") or "") or None,
            "closed_at": None, "status": normalize(source.get("complaint_status_title") or "") or None,
            "privacy_flags": flags, "privacy_status": "pending_human_review", "privacy_review_required": True,
        })
    _write_jsonl(minimal_path, minimal_rows)
    _write_jsonl(prepared_path, prepared_rows)
    manifest = {
        "source_id": SOURCE_ID, "data_kind": "real", "text_kind": "narrative",
        "source_url": source_url, "license": license_name,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "publisher_csv_sha256": full_hash, "publisher_csv_bytes": full_csv.stat().st_size,
        "minimal_path": minimal_path.relative_to(data_root).as_posix(),
        "minimal_sha256": file_digest(minimal_path),
        "processed_path": prepared_path.relative_to(data_root).as_posix(),
        "processed_sha256": file_digest(prepared_path),
        "row_count": len(prepared_rows), "metrics": metrics,
        "category_distribution": dict(label_counts),
        "language_script_distribution": dict(language_counts),
        "privacy_flags": dict(flags_count), "human_reviewed_count": 0,
        "id_method": "SHA-256(source ID, publisher file checksum, CSV row ordinal); publisher CSV has no complaint ID column",
        "retention": "Delete full publisher CSV after minimized extract verification; retain minimized redacted local data only for authorized review, target 30 days pending owner policy",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(".partial")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publisher-csv", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("ml/data"))
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()
    result = minimize(args.publisher_csv, args.data_root, source_url=args.source_url, license_name=args.license, max_rows=args.max_rows)
    print(json.dumps({key: result[key] for key in ("source_id", "publisher_csv_sha256", "publisher_csv_bytes", "row_count", "minimal_sha256", "processed_sha256", "human_reviewed_count")}))


if __name__ == "__main__":
    main()
