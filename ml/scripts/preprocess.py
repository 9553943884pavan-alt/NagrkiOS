"""Normalize approved public exports without inventing missing labels.

Inputs and outputs stay in the ignored ml/data tree. No network or application access.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

VERSION = "1"
EMAIL = re.compile(r"(?<![\w.])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)")
PHONE = re.compile(r"(?<!\d)(?:\+?91[- .]?)?[6-9]\d{4}[- .]?\d{5}(?!\d)")
US_PHONE = re.compile(r"(?<!\d)(?:\+?1[- .]?)?\(?\d{3}\)?[- .]?\d{3}[- .]?\d{4}(?!\d)")
IDENTIFIER = re.compile(r"\b(?:\d{4}[- ]?\d{4}[- ]?\d{4}|[A-Z]{5}\d{4}[A-Z])\b", re.I)
ADDRESS = re.compile(r"\b\d{1,5}\s+(?:(?:[A-Za-z]+|\.)\s+){0,5}(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|nagar|marg)\b", re.I)
PERSON_HINT = re.compile(r"\b(?:my name is|name is|i am|this is mr|this is ms|s/o|d/o|w/o|श्री|श्रीमती)\b", re.I)
INTRODUCED_NAME = re.compile(r"(?i:\b(?:my name is|name is|this is mr|this is ms)\s+)(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})")
FIELDS = ("record_id", "source_id", "complaint_text", "text_kind", "language", "category", "category_source", "department", "urgency", "location", "created_at", "closed_at", "status", "privacy_review_required")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return " ".join(value.replace("\x00", " ").split())


def redact(value: str) -> tuple[str, list[str]]:
    found = []
    if INTRODUCED_NAME.search(value):
        found.append("possible_name")
        value = INTRODUCED_NAME.sub("[NAME]", value)
    for label, pattern in (("email", EMAIL), ("phone", PHONE), ("phone", US_PHONE), ("identifier", IDENTIFIER), ("address", ADDRESS)):
        if pattern.search(value):
            found.append(label)
            value = pattern.sub(f"[{label.upper()}]", value)
    if PERSON_HINT.search(value):
        found.append("possible_name")
    return value, sorted(set(found))


def language_hint(value: str) -> str | None:
    devanagari = sum("\u0900" <= char <= "\u097f" for char in value)
    latin = sum("a" <= char.lower() <= "z" for char in value)
    if devanagari and latin:
        return "mixed_hindi_latin"
    if devanagari:
        return "devanagari_script"
    if latin:
        return "latin_script"
    return None


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        if path.suffix.lower() == ".csv":
            yield from csv.DictReader(stream)
        elif path.suffix.lower() == ".json":
            data = json.load(stream)
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise ValueError("JSON source must be an array of objects")
            yield from data
        elif path.suffix.lower() in (".jsonl", ".ndjson"):
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("JSONL rows must be objects")
                    yield value
        else:
            raise ValueError("Only CSV, JSON and JSONL are supported")


def convert(row: dict, source_id: str, position: int, fields: dict[str, str], text_kind: str = "narrative") -> tuple[dict | None, list[str]]:
    raw_text = row.get(fields["text"], "")
    if not isinstance(raw_text, str):
        return None, ["invalid_text"]
    cleaned = normalize(raw_text)
    if not cleaned:
        return None, ["empty_text"]
    cleaned, signals = redact(cleaned)
    source_record_id = str(row.get(fields.get("id", "")) or position)
    def optional(name: str) -> str | None:
        key = fields.get(name)
        value = row.get(key) if key else None
        return normalize(str(value)) if value is not None and str(value).strip() else None
    record = {
        "record_id": digest(f"{source_id}\0{source_record_id}"),
        "source_id": source_id,
        "complaint_text": cleaned,
        "text_kind": text_kind,
        "language": optional("language") or language_hint(cleaned),
        "category": optional("category"),
        "category_source": "source_provided" if optional("category") else None,
        "department": optional("department"),
        "urgency": optional("urgency"),
        "location": None,  # Public exports can contain precise home addresses; keep only in raw source.
        "created_at": optional("created_at"),
        "closed_at": optional("closed_at"),
        "status": optional("status"),
        "privacy_review_required": True,  # Regex cannot prove names/addresses are absent.
    }
    return record, signals


def process(input_path: Path, output_path: Path, source_id: str, fields: dict[str, str], text_kind: str = "narrative") -> dict:
    if not fields.get("text"):
        raise ValueError("An explicit complaint-text field is required")
    if output_path.exists():
        manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (existing.get("source_id") == source_id and existing.get("field_mapping") == fields
                    and existing.get("text_kind") == text_kind and existing.get("preprocess_version") == VERSION
                    and existing.get("input_sha256") == file_digest(input_path)
                    and existing.get("output_sha256") == file_digest(output_path)):
                return existing
        raise FileExistsError(f"Existing processed dataset differs or has no verified manifest: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".partial")
    counts: Counter = Counter()
    labels: Counter = Counter()
    seen: set[str] = set()
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for position, row in enumerate(rows(input_path), 1):
                counts["input"] += 1
                record, signals = convert(row, source_id, position, fields, text_kind)
                if record is None:
                    counts[signals[0]] += 1
                    continue
                if record["record_id"] in seen:
                    counts["duplicate_source_id"] += 1
                    continue
                seen.add(record["record_id"])
                counts["output"] += 1
                for signal in signals:
                    counts[f"privacy_{signal}"] += 1
                if record["category"]:
                    labels[record["category"]] += 1
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"source_id": source_id, "preprocess_version": VERSION, "input_sha256": file_digest(input_path), "output_sha256": file_digest(output_path), "counts": dict(counts), "category_distribution": dict(labels), "field_mapping": fields, "text_kind": text_kind, "privacy_review_required_for_all_records": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--text-field", required=True)
    parser.add_argument("--text-kind", choices=("narrative", "descriptor_label"), required=True)
    for name in ("id", "category", "department", "urgency", "language", "created_at", "closed_at", "status"):
        parser.add_argument(f"--{name.replace('_', '-')}-field")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    registry = json.loads((workspace / "configs" / "sources.json").read_text(encoding="utf-8"))
    source = next((entry for entry in registry["sources"] if entry["id"] == args.source_id), None)
    if source is None or source.get("status") != "approved" or source.get("approved_for_download") is not True:
        parser.error("Source is not approved for preprocessing")
    collected_manifest = workspace / "data" / "manifests" / f"{args.source_id}.json"
    if not collected_manifest.exists():
        parser.error("Verified acquisition manifest is required")
    provenance = json.loads(collected_manifest.read_text(encoding="utf-8"))
    expected_path = workspace / "data" / provenance["path"]
    if (provenance.get("source_id") != args.source_id or provenance.get("status") != "verified"
            or provenance.get("source_url") != source["url"]
            or args.input.resolve() != expected_path.resolve() or file_digest(args.input) != provenance["sha256"]):
        parser.error("Raw input does not match the verified acquisition manifest")
    fields = {name: getattr(args, f"{name}_field") for name in ("id", "category", "department", "urgency", "language", "created_at", "closed_at", "status") if getattr(args, f"{name}_field")}
    fields["text"] = args.text_field
    result = process(args.input, args.output, args.source_id, fields, args.text_kind)
    manifest = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "manifest": str(manifest), "counts": result["counts"]}))


if __name__ == "__main__":
    main()
