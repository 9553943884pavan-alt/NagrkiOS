"""Synthetic fixtures only; real civic narratives never appear in tests."""
import csv
import json

import pytest

from ml.scripts.minimize_opencity import minimize
from ml.scripts.split import assign
from ml.scripts.validate import validate


URL = "https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f"


def fixture_csv(path):
    fields = ["title", "description", "category_title", "sub_category_title", "civic_agency_title", "created_at", "complaint_status_title", "address", "latitude", "longitude", "ward_title", "comment_count"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"title": "Broken tap near ward 4", "description": "The public tap is broken; call 9876543210 or test@example.org near ward 4", "category_title": "Water", "sub_category_title": "Tap", "civic_agency_title": "City Water", "created_at": "2020-01-01", "complaint_status_title": "Open", "address": "12 Main Road", "latitude": "12.3456", "longitude": "77.1234", "ward_title": "Example", "comment_count": "7"})
        writer.writerow({"title": "Other", "description": "", "category_title": "Roads"})


def test_minimization_discards_sensitive_columns_and_preserves_source_label(tmp_path):
    source = tmp_path / "publisher.csv"
    fixture_csv(source)
    result = minimize(source, tmp_path / "data", source_url=URL, license_name="CC BY-SA 2.0", max_rows=10)
    assert result["metrics"]["publisher_rows"] == 2
    assert result["metrics"]["eligible_description_category_rows"] == 1
    assert result["row_count"] == 1
    raw = [json.loads(line) for line in (tmp_path / "data" / result["minimal_path"]).read_text(encoding="utf-8").splitlines()]
    prepared = [json.loads(line) for line in (tmp_path / "data" / result["processed_path"]).read_text(encoding="utf-8").splitlines()]
    assert len(raw) == len(prepared) == 1
    assert set(raw[0]) == {"record_id", "title", "description", "category_title", "sub_category_title", "civic_agency_title", "created_at", "complaint_status_title"}
    assert "9876543210" not in raw[0]["description"]
    assert "test@example.org" not in raw[0]["description"]
    assert "12 Main Road" not in json.dumps(raw[0])
    assert prepared[0]["category"] == "Water"
    assert prepared[0]["category_source"] == "source_provided"
    assert prepared[0]["department"] is None and prepared[0]["urgency"] is None
    assert prepared[0]["privacy_status"] == "pending_human_review"
    assert "possible_location" in prepared[0]["privacy_flags"]
    split_path = tmp_path / "split.json"
    split_path.write_text(json.dumps(assign(prepared, template_mode=True)), encoding="utf-8")
    assert validate(tmp_path / "data" / result["processed_path"], split_path, tmp_path / "data/manifests/opencity_ichangemycity_2019_2022_phase3.json")["ok"]
    assert minimize(source, tmp_path / "data", source_url=URL, license_name="CC BY-SA 2.0", max_rows=10) == result


def test_minimization_rejects_unverified_source(tmp_path):
    source = tmp_path / "publisher.csv"
    fixture_csv(source)
    with pytest.raises(ValueError, match="provenance"):
        minimize(source, tmp_path / "data", source_url="https://mirror.example/copy.csv", license_name="CC BY-SA 2.0")


def test_cp1252_publisher_text_preserves_punctuation(tmp_path):
    source = tmp_path / "publisher.csv"
    with source.open("w", encoding="cp1252", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted({"title", "description", "category_title", "sub_category_title", "civic_agency_title", "created_at", "complaint_status_title"}))
        writer.writeheader()
        writer.writerow({"title": "Road", "description": "The road’s surface is broken", "category_title": "Road"})
    result = minimize(source, tmp_path / "data", source_url=URL, license_name="CC BY-SA 2.0", max_rows=1)
    assert result["metrics"]["decoded_encoding"] == "cp1252"
    row = json.loads((tmp_path / "data" / result["processed_path"]).read_text(encoding="utf-8"))
    assert "road’s surface" in row["complaint_text"]
