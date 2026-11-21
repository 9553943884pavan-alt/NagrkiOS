import json

from ml.scripts.privacy_scan import scan


def test_scan_returns_only_aggregate_counts(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps({"record_id": "private-id", "title": "See https://example.org/case/abc", "description": "PIN 560001; account 12345678"}) + "\n", encoding="utf-8")
    result = scan(path, ("title", "description"))
    assert result["rows"] == 1
    assert result["matching_rows"]["url"] == 1
    assert result["matching_rows"]["six_digit_number"] == 1
    assert result["matching_rows"]["long_number"] == 1
    rendered = json.dumps(result)
    assert "private-id" not in rendered
    assert "560001" not in rendered
    assert "https://example.org" not in rendered
