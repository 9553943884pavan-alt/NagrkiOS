"""Privacy hardening tests use fabricated fixture text only."""
import json

from ml.scripts.harden_review_text import harden, harden_text
from ml.scripts.preprocess import file_digest


def test_harden_patterns_cover_urls_numbers_and_pin_like():
    text, flags = harden_text("See https://example.org/abc, call 12345678, PIN 560001")
    assert "example.org" not in text and "12345678" not in text and "560001" not in text
    assert set(flags) == {"url", "long_number", "pin_like"}


def test_harden_preserves_lineage_and_nulls_sentinel_label(tmp_path):
    minimal = tmp_path / "minimal.jsonl"
    processed = tmp_path / "processed.jsonl"
    manifest = tmp_path / "manifest.json"
    source = {"record_id": "a" * 64, "title": "Report www.example.org", "description": "The street light near PIN 560001 is broken", "category_title": "NULL"}
    prepared = {"record_id": "a" * 64, "complaint_text": source["description"], "category": "NULL", "category_source": "source_provided", "privacy_flags": [], "privacy_status": "pending_human_review", "privacy_review_required": True}
    minimal.write_text(json.dumps(source) + "\n", encoding="utf-8")
    processed.write_text(json.dumps(prepared) + "\n", encoding="utf-8")
    metadata = {"row_count": 1, "minimal_sha256": file_digest(minimal), "processed_sha256": file_digest(processed)}
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    result = harden(minimal, processed, manifest)
    after = json.loads(processed.read_text(encoding="utf-8"))
    raw = json.loads(minimal.read_text(encoding="utf-8"))
    assert after["category"] is None and after["category_source"] is None
    assert after["source_category_raw"] == "NULL"
    assert after["record_id"] == source["record_id"]
    assert after["complaint_text"] == raw["description"]
    assert "560001" not in after["complaint_text"]
    assert "www.example.org" not in raw["title"]
    assert result["source_label_sentinel_count"] == 1
    assert harden(minimal, processed, manifest) == result
