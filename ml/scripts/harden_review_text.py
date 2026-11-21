"""Second-pass local redaction for the verified OpenCity review collection.

Changes only ignored research files. Prints aggregate counts, never narrative text.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

from ml.scripts.preprocess import file_digest

URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+")
LONG_NUMBER = re.compile(r"(?<!\d)\d{8,}(?!\d)")
PIN_LIKE = re.compile(r"(?<!\d)\d{6}(?!\d)")
SENTINELS = {"NULL", "N/A", "NA", "UNKNOWN", "NONE"}
VERSION = "2"


def harden_text(text: str) -> tuple[str, list[str]]:
    flags = []
    for label, pattern, replacement in (("url", URL, "[URL]"), ("long_number", LONG_NUMBER, "[NUMBER]"), ("pin_like", PIN_LIKE, "[PIN]")):
        if pattern.search(text):
            flags.append(label)
            text = pattern.sub(replacement, text)
    return text, flags


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    temporary = path.with_suffix(path.suffix + ".hardening_partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return temporary


def harden(minimal_path: Path, processed_path: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("redaction_hardening_version") == VERSION:
        if file_digest(minimal_path) != manifest.get("minimal_sha256") or file_digest(processed_path) != manifest.get("processed_sha256"):
            raise ValueError("Hardened output checksum mismatch")
        return manifest
    if file_digest(minimal_path) != manifest.get("minimal_sha256") or file_digest(processed_path) != manifest.get("processed_sha256"):
        raise ValueError("Input checksum does not match source manifest")
    minimal = [json.loads(line) for line in minimal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    prepared = [json.loads(line) for line in processed_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(minimal) != len(prepared) or len(prepared) != manifest.get("row_count"):
        raise ValueError("Input row counts differ")
    by_id = {row["record_id"]: row for row in minimal}
    if len(by_id) != len(minimal) or set(by_id) != {row["record_id"] for row in prepared}:
        raise ValueError("Minimal and processed record IDs differ")
    counts: Counter = Counter()
    missing_labels = 0
    for row in prepared:
        raw = by_id[row["record_id"]]
        original_description = raw["description"]
        title, title_flags = harden_text(raw["title"])
        description, description_flags = harden_text(raw["description"])
        raw["title"], raw["description"] = title, description
        # The processed narrative must match the minimized source description.
        if row["complaint_text"] != original_description:
            raise ValueError("Minimal and processed narratives differ")
        row["complaint_text"] = description
        flags = set(row.get("privacy_flags", [])) | set(title_flags) | set(description_flags)
        row["privacy_flags"] = sorted(flags)
        counts.update(title_flags)
        counts.update(description_flags)
        if isinstance(row.get("category"), str) and row["category"].strip().upper() in SENTINELS:
            raw_label = row["category"]
            row["source_category_raw"] = raw_label
            row["category"] = None
            row["category_source"] = None
            missing_labels += 1
        row["privacy_status"] = "pending_human_review"
        row["privacy_review_required"] = True
    minimal_temp = _write_jsonl(minimal_path, minimal)
    processed_temp = _write_jsonl(processed_path, prepared)
    try:
        new_minimal_hash = file_digest(minimal_temp)
        new_processed_hash = file_digest(processed_temp)
        manifest["previous_minimal_sha256"] = manifest["minimal_sha256"]
        manifest["previous_processed_sha256"] = manifest["processed_sha256"]
        manifest["minimal_sha256"] = new_minimal_hash
        manifest["processed_sha256"] = new_processed_hash
        manifest["redaction_hardening_version"] = VERSION
        manifest["hardening_pattern_counts"] = dict(counts)
        manifest["source_label_sentinel_count"] = missing_labels
        os.replace(minimal_temp, minimal_path)
        os.replace(processed_temp, processed_path)
        temporary_manifest = manifest_path.with_suffix(".hardening_partial")
        temporary_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary_manifest, manifest_path)
    finally:
        minimal_temp.unlink(missing_ok=True)
        processed_temp.unlink(missing_ok=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimal", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = harden(args.minimal, args.processed, args.manifest)
    print(json.dumps({key: result[key] for key in ("row_count", "redaction_hardening_version", "minimal_sha256", "processed_sha256", "source_label_sentinel_count", "hardening_pattern_counts")}))


if __name__ == "__main__":
    main()
