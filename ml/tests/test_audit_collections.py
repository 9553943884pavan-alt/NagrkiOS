"""Cross-source separation and leakage checks for research collections."""
import json

from ml.scripts.audit_collections import audit


def collection(tmp_path, source_id, kind, records, split_name="train"):
    processed = tmp_path / f"{source_id}.jsonl"
    split = tmp_path / f"{source_id}.split.json"
    processed.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    split.write_text(json.dumps({"splits": {name: [row["record_id"] for row in records] if name == split_name else [] for name in ("train", "validation", "test")}}), encoding="utf-8")
    return {"source_id": source_id, "kind": kind, "processed": str(processed), "split": str(split)}


def test_synthetic_requires_marker_and_generated_label_provenance(tmp_path):
    row = {"record_id": "a" * 64, "source_id": "nandi", "complaint_text": "The village water pipeline has been broken for four days and the taps are dry.", "category": "Water", "category_source": "synthetic_generated", "urgency": "high", "urgency_source": "synthetic_generated", "data_kind": "synthetic"}
    entry = collection(tmp_path, "nandi", "synthetic", [row])
    assert audit([entry])["ok"]
    row["data_kind"] = "real"
    entry = collection(tmp_path, "nandi", "synthetic", [row])
    result = audit([entry])
    assert not result["ok"]
    assert any("synthetic marker" in issue for issue in result["issues"])


def test_cross_source_related_cases_are_quarantined(tmp_path):
    text = "The water pipeline outside our market has been leaking for three days without repair"
    real = {"record_id": "a" * 64, "source_id": "indian_real", "complaint_text": text, "text_kind": "narrative", "data_kind": "real", "privacy_status": "pending_human_review"}
    synthetic = {"record_id": "b" * 64, "source_id": "nandi", "complaint_text": text, "text_kind": "narrative", "data_kind": "synthetic"}
    result = audit([
        collection(tmp_path, "indian_real", "real_narrative", [real], "test"),
        collection(tmp_path, "nandi", "synthetic", [synthetic], "train"),
    ])
    assert not result["ok"]
    assert result["cross_source_related_groups"] == 1
    assert result["cross_split_related_groups"] == 1
    assert result["quarantined_record_ids"] == ["a" * 64, "b" * 64]
