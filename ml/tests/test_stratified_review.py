import json

from ml.scripts.stratified_review import choose


def test_review_queue_has_only_ids_and_aggregate_metadata():
    rows = [
        {"record_id": f"{index:064x}", "complaint_text": f"Private case text {index}", "category": "Road" if index < 8 else "Water", "language": "latin_script", "privacy_flags": ["possible_location"] if index % 2 else []}
        for index in range(12)
    ]
    split = {"splits": {"train": [row["record_id"] for row in rows[:4]], "validation": [row["record_id"] for row in rows[4:8]], "test": [row["record_id"] for row in rows[8:]]}}
    result = choose(rows, split, count=9)
    assert result["counts"]["selected"] == 9
    assert set(result["counts"]["by_split"]) == {"train", "validation", "test"}
    assert result["counts"]["flagged"] > 0
    assert result["counts"]["risk_types_covered"] == ["possible_location"]
    assert "Private case text" not in json.dumps(result)


def test_review_queue_covers_each_observed_privacy_risk_type():
    rows = [
        {"record_id": f"{index:064x}", "category": "Road", "privacy_flags": [flag]}
        for index, flag in enumerate(("email", "phone", "address", "possible_name", "url", "handle"))
    ]
    rows += [{"record_id": f"{index:064x}", "category": "Water", "privacy_flags": []} for index in range(6, 12)]
    split = {"splits": {"train": [row["record_id"] for row in rows[:4]], "validation": [row["record_id"] for row in rows[4:8]], "test": [row["record_id"] for row in rows[8:]]}}
    result = choose(rows, split, count=12)
    assert set(result["counts"]["risk_types_covered"]) == {"email", "phone", "address", "possible_name", "url", "handle"}
