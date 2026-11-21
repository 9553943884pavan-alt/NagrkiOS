import json

from ml.scripts.readiness_matrix import summarize


def test_generated_labels_never_count_as_genuine(tmp_path):
    operational = tmp_path / "nyc.jsonl"
    synthetic = tmp_path / "nandi.jsonl"
    operational.write_text(json.dumps({"source_id": "nyc", "text_kind": "descriptor_label", "category": "Water", "category_source": "source_provided", "language": "latin_script"}) + "\n", encoding="utf-8")
    synthetic.write_text(json.dumps({"source_id": "nandi", "text_kind": "narrative", "data_kind": "synthetic", "category": "Water", "category_source": "synthetic_generated", "language": "Hindi", "urgency": "high", "urgency_source": "synthetic_generated"}) + "\n", encoding="utf-8")
    result = summarize([
        {"source_id": "nyc", "kind": "real_operational", "processed": str(operational)},
        {"source_id": "nandi", "kind": "synthetic", "processed": str(synthetic)},
    ])
    assert result["real_narrative_records"] == 0
    assert result["genuine_category_by_language"] == {}
    assert result["synthetic_category_by_language"] == {"Water": {"Hindi": 1}}
    assert result["independent_detection_labels"] == {}


def test_real_source_annotations_are_independent_counts(tmp_path):
    real = tmp_path / "real.jsonl"
    real.write_text(json.dumps({"source_id": "real", "text_kind": "narrative", "data_kind": "real", "category": "Water Supply", "category_source": "source_provided", "complaint_label": "complaint", "label_source": "dataset_annotation", "language": "Hindi", "privacy_status": "reviewed_approved", "privacy_review_required": False}) + "\n", encoding="utf-8")
    result = summarize([{"source_id": "real", "kind": "real_narrative", "processed": str(real)}])
    assert result["real_narrative_records"] == 1
    assert result["usable_privacy_reviewed_real_narratives"] == 1
    assert result["genuine_category_by_language"] == {"Water Supply": {"Hindi": 1}}
    assert result["independent_detection_labels"] == {"complaint": 1}


def test_pending_real_narrative_remains_candidate_only(tmp_path):
    real = tmp_path / "pending.jsonl"
    real.write_text(json.dumps({"source_id": "opencity", "text_kind": "narrative", "data_kind": "real", "category": "Water Supply", "category_source": "source_provided", "language": "latin_script", "privacy_status": "pending_human_review", "privacy_review_required": True}) + "\n", encoding="utf-8")
    result = summarize([{"source_id": "opencity", "kind": "real_narrative", "processed": str(real)}])
    assert result["real_narrative_records"] == 1
    assert result["usable_privacy_reviewed_real_narratives"] == 0
    assert result["genuine_category_by_language"] == {}
    assert result["candidate_source_category_by_script_or_language"] == {"Water Supply": {"latin_script": 1}}
