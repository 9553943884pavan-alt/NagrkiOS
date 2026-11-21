"""Bounded Nandi acquisition and synthetic provenance tests; no network."""
from __future__ import annotations

import json

import pytest

from ml.scripts import acquire_nandi as nandi


def fake_row(index: int, language: str, domain: str) -> dict:
    return {"row_idx": index, "row": {"id": f"row-{index}", "text": f"The public service counter has not responded to my case for {index} days.", "category": "gov.service_delay" if domain != "none" else "none.out_of_scope", "domain": domain, "urgency": "P2", "language": language}}


def test_select_balances_language_and_domain_without_inventing_rows():
    rows = [fake_row(index, language, domain) for index, (language, domain) in enumerate((lang, group) for lang in nandi.LANGUAGES for group in ("gov", "none", "tel") for _ in range(25))]
    selected, stats = nandi.select(rows)
    assert len(selected) == 150
    assert stats["shortages"] == {}
    assert stats["language_counts"] == {"hi": 50, "hinglish": 50, "en": 50}
    assert len({row["id"] for row in selected}) == 150


def test_transformation_preserves_generated_label_provenance_and_redacts():
    row = fake_row(1, "hi", "gov")["row"]
    row["text"] += " Contact rani@example.org."
    raw, prepared = nandi.transform(row)
    assert raw["data_kind"] == prepared["data_kind"] == "synthetic"
    assert prepared["category_source"] == "synthetic_generated"
    assert prepared["urgency_source"] == "synthetic_generated"
    assert prepared["department"] is None
    assert "rani@example.org" not in prepared["complaint_text"]
    assert raw["text"] != prepared["complaint_text"]


def test_acquire_reuses_verified_manifest_and_blocks_changed_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(nandi, "OFFSETS", (0,))
    monkeypatch.setattr(nandi, "LENGTH", 3)
    calls = []

    def fetch(url):
        calls.append(url)
        if "/api/datasets/" in url:
            return {"sha": nandi.REVISION, "private": False, "gated": False, "tags": ["license:apache-2.0"]}
        return {"partial": False, "num_rows_total": 116199, "rows": [fake_row(0, "hi", "gov"), fake_row(1, "hinglish", "none"), fake_row(2, "en", "tel")]}

    first = nandi.acquire(tmp_path, fetch=fetch)
    assert first["row_count"] == 3
    assert first["human_reviewed_labels"] == 0
    assert len(calls) == 3
    second = nandi.acquire(tmp_path, fetch=lambda _: pytest.fail("redownloaded verified source"))
    assert second == first
    raw = tmp_path / first["raw_path"]
    raw.write_text(raw.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        nandi.acquire(tmp_path, fetch=fetch)


def test_changed_license_or_revision_blocks_acquisition(tmp_path):
    with pytest.raises(ValueError, match="revision"):
        nandi.acquire(tmp_path, fetch=lambda _: {"sha": "changed", "private": False, "gated": False, "tags": ["license:apache-2.0"]})
    with pytest.raises(ValueError, match="license"):
        nandi.acquire(tmp_path, fetch=lambda _: {"sha": nandi.REVISION, "private": False, "gated": False, "tags": []})
