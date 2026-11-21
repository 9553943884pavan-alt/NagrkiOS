"""Offline pipeline guarantees that protect labels, privacy and evaluation splits."""
from __future__ import annotations

import json

import pytest

from ml.scripts.preprocess import convert, process, redact
from ml.scripts.profile import profile
from ml.scripts.review_sample import sample
from ml.scripts.split import assign, related, template_related
from ml.scripts.validate import validate


def test_redaction_and_uncertain_names_are_flagged():
    text, signals = redact("My name is Rani. Email rani@example.org or call +91 9876543210 at 12 Main Road.")
    assert "rani@example.org" not in text
    assert "Rani" not in text
    assert "9876543210" not in text
    assert "12 Main Road" not in text
    assert set(signals) == {"email", "phone", "address", "possible_name"}


def test_missing_labels_stay_null_and_location_is_withheld():
    row, _ = convert({"body": "Broken water line near school", "address": "12 Main Road"}, "sample", 1, {"text": "body"})
    assert row["category"] is None
    assert row["category_source"] is None
    assert row["department"] is None
    assert row["urgency"] is None
    assert row["location"] is None
    assert row["privacy_review_required"] is True


def test_near_duplicates_share_split_and_manifest_validates(tmp_path):
    raw = tmp_path / "source.json"
    raw.write_text(json.dumps([
        {"id": "one", "body": "Water pipeline has been broken by the market for three days.", "category": "Water Supply"},
        {"id": "two", "body": "Water pipeline has been broken by the market for three days!", "category": "Water Supply"},
        {"id": "three", "body": "The school roof leaks in every classroom during the rain."},
    ]), encoding="utf-8")
    processed = tmp_path / "prepared.jsonl"
    manifest = process(raw, processed, "test_source", {"id": "id", "text": "body", "category": "category"})
    records = [json.loads(line) for line in processed.read_text(encoding="utf-8").splitlines()]
    assert manifest["counts"]["output"] == 3
    assert records[2]["category"] is None
    assert related(records[0]["complaint_text"], records[1]["complaint_text"])
    split = assign(records)
    first = records[0]["record_id"]
    second = records[1]["record_id"]
    assert any(first in members and second in members for members in split["splits"].values())
    split_path = tmp_path / "split.json"
    manifest_path = tmp_path / "prepared.jsonl.manifest.json"
    split_path.write_text(json.dumps(split), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate(processed, split_path, manifest_path)["ok"]
    metrics = profile(records, split)
    assert metrics["exact_duplicate_rows"] == 1
    assert metrics["missing_by_field"]["urgency"] == 3
    review = sample(split, per_split=2)
    assert "complaint_text" not in json.dumps(review)
    assert sum(map(len, review["case_ids_by_split"].values())) <= 6
    assert process(raw, processed, "test_source", {"id": "id", "text": "body", "category": "category"}) == manifest
    with pytest.raises(FileExistsError):
        process(raw, processed, "test_source", {"text": "body"})


def test_checksum_and_split_tampering_detected(tmp_path):
    raw = tmp_path / "source.jsonl"
    raw.write_text('{"text":"A complaint about a broken school gate"}\n', encoding="utf-8")
    processed = tmp_path / "prepared.jsonl"
    manifest = process(raw, processed, "test_source", {"text": "text"})
    records = [json.loads(line) for line in processed.read_text(encoding="utf-8").splitlines()]
    split = assign(records)
    split_path = tmp_path / "split.json"
    manifest_path = tmp_path / "manifest.json"
    split_path.write_text(json.dumps(split), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    processed.write_text(processed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = validate(processed, split_path, manifest_path)
    assert not result["ok"]
    assert "processed checksum mismatch" in result["issues"]


def test_template_variants_are_grouped():
    left = "The water pipeline outside house 12 has been leaking for three days and no one has repaired it"
    right = "The water pipeline outside house 34 has been leaking for three days and no one has repaired it"
    assert template_related(left, right)
    records = [
        {"record_id": "a" * 64, "source_id": "synthetic", "complaint_text": left},
        {"record_id": "b" * 64, "source_id": "synthetic", "complaint_text": right},
    ]
    result = assign(records, template_mode=True)
    assert any(len(members) == 2 for members in result["splits"].values())


def test_validator_rejects_unmarked_generated_labels(tmp_path):
    row, _ = convert({"body": "The street drain outside the market is blocked for days", "category": "Waste"}, "synthetic_source", 1, {"text": "body", "category": "category"})
    row["category_source"] = "synthetic_generated"
    row["urgency"] = "high"
    row["urgency_source"] = "synthetic_generated"
    row["data_kind"] = "synthetic"
    processed = tmp_path / "rows.jsonl"
    splits = tmp_path / "split.json"
    processed.write_text(json.dumps(row) + "\n", encoding="utf-8")
    splits.write_text(json.dumps(assign([row], template_mode=True)), encoding="utf-8")
    assert validate(processed, splits)["ok"]
    row.pop("data_kind")
    processed.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert not validate(processed, splits)["ok"]
