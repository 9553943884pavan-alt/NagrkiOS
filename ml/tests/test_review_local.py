"""Synthetic-only checks for the offline human review gate."""
from __future__ import annotations

import json
import sqlite3
import hashlib

import pytest
import ml.scripts.review_local as review_local_module
from ml.scripts.preprocess import file_digest

from ml.scripts.review_local import (
    adjudication_material,
    export_manifest,
    initialize,
    review_status,
    reviewer_case,
    reviewer_progress,
    submit_adjudication,
    submit_review,
    validate_review,
)


RECORD_ID = "a" * 64
OTHER_ID = "b" * 64
IDENTITIES = {
    "ReviewerA": ("reviewer", "synthetic passphrase one"),
    "ReviewerB": ("reviewer", "synthetic passphrase two"),
    "Adjudicator": ("adjudicator", "synthetic passphrase three"),
}
APPROVAL = {
    "authorship": "citizen",
    "identifiers_remaining": "no",
    "privacy_disposition": "approve",
    "category_correctness": "yes",
    "verified_language": "english",
    "duplicate_status": "no",
    "sanitized_notes": ["none"],
}
ADJUDICATION = {
    "final_disposition": "approve",
    "final_authorship": "citizen",
    "final_identifiers_remaining": "no",
    "final_category_correctness": "yes",
    "final_language": "english",
    "final_duplicate_status": "no",
    "sanitized_notes": ["none"],
}


def status(db):
    return review_status(db, RECORD_ID, "ReviewerA", IDENTITIES["ReviewerA"][1])


@pytest.fixture
def review_store(tmp_path):
    queue = tmp_path / "queue.json"
    processed = tmp_path / "processed.jsonl"
    split = tmp_path / "split.json"
    db = tmp_path / "reviews" / "decisions.sqlite3"
    queue.write_text(json.dumps({"items": [{"record_id": RECORD_ID, "split": "train"}]}), encoding="utf-8")
    split.write_text(json.dumps({"splits": {"train": [RECORD_ID], "validation": [], "test": []}}), encoding="utf-8")
    processed.write_text(json.dumps({
        "record_id": RECORD_ID,
        "source_id": "opencity_ichangemycity_2019_2022",
        "data_kind": "real",
        "privacy_status": "pending_human_review",
        "complaint_text": "A synthetic test report about a broken street light.",
        "category": "Street Lighting",
        "source_subcategory": "Lamp outage",
        "source_agency": "Example Civic Office",
        "privacy_flags": ["possible_indirect_identifier"],
        "language": "latin_script",
    }) + "\n", encoding="utf-8")
    initialize(db, queue, processed, IDENTITIES, split_path=split, secure_permissions=False)
    return db, queue, processed, split


def test_two_reviews_require_explicit_adjudication(review_store):
    db, _, _, _ = review_store
    assert status(db)["state"] == "awaiting_reviews"
    case = reviewer_case(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID)
    assert case["redacted_text"].startswith("A synthetic test")
    assert case["source_subcategory"] == "Lamp outage"
    assert "reviews" not in case and "adjudication" not in case

    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    assert status(db)["state"] == "awaiting_reviews"
    assert reviewer_case(db, "ReviewerB", IDENTITIES["ReviewerB"][1], RECORD_ID)["own_submitted"] is False
    submit_review(db, "ReviewerB", IDENTITIES["ReviewerB"][1], RECORD_ID, APPROVAL)
    pending = status(db)
    assert pending["state"] == "awaiting_adjudication"
    assert pending["adjudication"] is None
    assert pending["review_count"] == 2 and pending["reviews"] == []
    assert pending["eligible"] is False
    with pytest.raises(PermissionError):
        adjudication_material(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID)
    assert len(adjudication_material(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID)["reviews"]) == 2

    submit_adjudication(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID, ADJUDICATION)
    final = status(db)
    assert final["state"] == "adjudicated_approved"
    assert final["eligible"] is True
    assert len(final["reviews"]) == 2
    assert final["adjudication"]["actor_id"] == "Adjudicator"
    assert all(event["event_hash"] for event in final["reviews"])


def test_review_access_and_write_once(review_store):
    db, _, _, _ = review_store
    with pytest.raises(PermissionError):
        review_status(db, RECORD_ID, "ReviewerA", "bad passphrase")
    with pytest.raises(PermissionError):
        reviewer_case(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID)
    with pytest.raises(PermissionError):
        reviewer_case(db, "ReviewerA", "wrong passphrase", RECORD_ID)
    with pytest.raises(PermissionError):
        submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], OTHER_ID, APPROVAL)
    with pytest.raises(ValueError):
        submit_adjudication(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID, ADJUDICATION)
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    with pytest.raises(sqlite3.IntegrityError):
        submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM review_events")


def test_conflicting_review_blocks_approval_and_allows_explicit_exclusion(review_store):
    db, _, _, _ = review_store
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    conflict = {**APPROVAL, "authorship": "staff_note", "privacy_disposition": "exclude"}
    submit_review(db, "ReviewerB", IDENTITIES["ReviewerB"][1], RECORD_ID, conflict)
    with pytest.raises(ValueError):
        submit_adjudication(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID, ADJUDICATION)
    submit_adjudication(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID,
                        {**ADJUDICATION, "final_disposition": "exclude", "final_authorship": "staff_note"})
    assert status(db)["state"] == "adjudicated_excluded"


def test_input_integrity_and_note_controls(review_store):
    db, queue, _, _ = review_store
    with pytest.raises(ValueError):
        validate_review({**APPROVAL, "sanitized_notes": ["Call 9876543210 for details"]})
    with pytest.raises(ValueError):
        validate_review({**APPROVAL, "identifiers_remaining": "uncertain"})
    queue.write_text(json.dumps({"items": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="input changed"):
        status(db)


def test_frozen_split_tampering_fails_closed(review_store):
    db, _, _, split = review_store
    split.write_text(json.dumps({"splits": {"train": [], "validation": [RECORD_ID], "test": []}}), encoding="utf-8")
    with pytest.raises(ValueError, match="input changed"):
        status(db)


def test_event_chain_detects_database_tampering(review_store):
    db, _, _, _ = review_store
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER no_event_update")
        conn.execute("UPDATE review_events SET payload_json='{}' WHERE seq=1")
    with pytest.raises(ValueError, match="hash mismatch"):
        status(db)


def test_export_snapshot_is_protected_write_once_and_has_no_case_text(review_store):
    db, _, _, split = review_store
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    output = db.parent / "evidence.json"
    with pytest.raises(PermissionError):
        export_manifest(db, output, "ReviewerA", IDENTITIES["ReviewerA"][1], secure_permissions=False)
    digest = export_manifest(db, output, "Adjudicator", IDENTITIES["Adjudicator"][1], secure_permissions=False)
    body = output.read_bytes()
    snapshot = json.loads(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert snapshot["record_count"] == 1
    assert snapshot["records"][0]["state"] == "awaiting_reviews"
    assert snapshot["records"][0]["eligible"] is False
    assert "complaint_text" not in body.decode("utf-8")
    assert "synthetic test report" not in body.decode("utf-8")
    assert snapshot["event_chain_head"] != "0" * 64
    assert snapshot["split_sha256"] == hashlib.sha256(split.read_bytes()).hexdigest()
    assert len(snapshot["records"][0]["reviews"]) == 1
    assert snapshot["records"][0]["reviews"][0]["actor_id"] == "ReviewerA"
    assert snapshot["records"][0]["reviews"][0]["decision"] == APPROVAL
    with pytest.raises(FileExistsError):
        export_manifest(db, output, "Adjudicator", IDENTITIES["Adjudicator"][1], secure_permissions=False)
    with pytest.raises(ValueError, match="beside"):
        export_manifest(db, db.parent.parent / "wrong.json", "Adjudicator", IDENTITIES["Adjudicator"][1], secure_permissions=False)


def test_missing_source_category_cannot_be_approved(tmp_path):
    queue = tmp_path / "queue.json"
    processed = tmp_path / "processed.jsonl"
    split = tmp_path / "split.json"
    db = tmp_path / "reviews.sqlite3"
    queue.write_text(json.dumps({"items": [{"record_id": RECORD_ID}]}), encoding="utf-8")
    split.write_text(json.dumps({"splits": {"train": [RECORD_ID], "validation": [], "test": []}}), encoding="utf-8")
    processed.write_text(json.dumps({"record_id": RECORD_ID, "source_id": "opencity_ichangemycity_2019_2022", "data_kind": "real", "privacy_status": "pending_human_review", "complaint_text": "Synthetic complaint.", "category": None}) + "\n", encoding="utf-8")
    initialize(db, queue, processed, IDENTITIES, split_path=split, secure_permissions=False)
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    submit_review(db, "ReviewerB", IDENTITIES["ReviewerB"][1], RECORD_ID, APPROVAL)
    with pytest.raises(ValueError, match="meaningful original source category"):
        submit_adjudication(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID, ADJUDICATION)


def test_progress_is_authenticated_and_tracks_only_own_submission(review_store):
    db, _, _, _ = review_store
    before = reviewer_progress(db, "ReviewerA", IDENTITIES["ReviewerA"][1])
    assert before == {"total": 1, "submitted": 0, "remaining": 1,
                      "next_record_id": RECORD_ID, "next_batch": None}
    with pytest.raises(PermissionError):
        reviewer_progress(db, "ReviewerA", "wrong passphrase")
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    after = reviewer_progress(db, "ReviewerA", IDENTITIES["ReviewerA"][1])
    peer = reviewer_progress(db, "ReviewerB", IDENTITIES["ReviewerB"][1])
    assert after["submitted"] == 1 and after["next_record_id"] is None
    assert peer["submitted"] == 0 and peer["next_record_id"] == RECORD_ID


def test_machine_cannot_set_training_eligibility(review_store):
    db, _, _, _ = review_store
    assert status(db)["training_eligibility"] is False
    assert status(db)["human_reviewer_a_decision"] is None
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    submit_review(db, "ReviewerB", IDENTITIES["ReviewerB"][1], RECORD_ID, APPROVAL)
    submit_adjudication(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID, ADJUDICATION)
    assert status(db)["eligible"] is True
    assert status(db)["training_eligibility"] is False


def test_reviewer_sees_hash_bound_machine_codes_only(review_store, monkeypatch):
    db, _, processed, split = review_store
    screening = processed.parent / "machine.jsonl"
    screening.write_text(json.dumps({"record_id": RECORD_ID, "machine_screening_status": "screened",
                                     "machine_privacy_risk": "uncertain", "privacy_evidence_codes": ["possible_location"],
                                     "review_batch": "audit_30", "training_eligibility": False,
                                     "unexpected_text": "synthetic hidden value"}) + "\n", encoding="utf-8")
    screening.with_suffix(".manifest.json").write_text(json.dumps({
        "output_sha256": file_digest(screening),
        "input_sha256": {"processed": file_digest(processed), "split": file_digest(split)}}), encoding="utf-8")
    monkeypatch.setattr(review_local_module, "DEFAULT_PROCESSED", processed)
    monkeypatch.setattr(review_local_module, "DEFAULT_SCREENING", screening)
    machine = reviewer_case(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID)["machine"]
    assert machine["machine_privacy_risk"] == "uncertain"
    assert machine["review_batch"] == "audit_30"
    assert "unexpected_text" not in machine


def test_adjudicator_sees_agreement_only_after_both_reviews(review_store):
    db, _, _, _ = review_store
    submit_review(db, "ReviewerA", IDENTITIES["ReviewerA"][1], RECORD_ID, APPROVAL)
    with pytest.raises(ValueError, match="Two independent reviews"):
        adjudication_material(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID)
    second = {**APPROVAL, "verified_language": "unknown"}
    submit_review(db, "ReviewerB", IDENTITIES["ReviewerB"][1], RECORD_ID, second)
    summary = adjudication_material(db, "Adjudicator", IDENTITIES["Adjudicator"][1], RECORD_ID)["agreement_summary"]
    assert summary["disagree"] == ["verified_language"]
    assert "authorship" in summary["agree"]


def test_reject_non_real_or_non_pending_source(tmp_path):
    queue = tmp_path / "queue.json"
    processed = tmp_path / "processed.jsonl"
    split = tmp_path / "split.json"
    db = tmp_path / "review.sqlite3"
    queue.write_text(json.dumps({"items": [{"record_id": RECORD_ID}]}), encoding="utf-8")
    split.write_text(json.dumps({"splits": {"train": [RECORD_ID], "validation": [], "test": []}}), encoding="utf-8")
    processed.write_text(json.dumps({"record_id": RECORD_ID, "data_kind": "synthetic", "privacy_status": "pending_human_review"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-pending or non-OpenCity real"):
        initialize(db, queue, processed, IDENTITIES, split_path=split, secure_permissions=False)
    assert not db.exists()


def test_default_permissions_refuse_review_store_outside_ignored_data(tmp_path):
    with pytest.raises(ValueError, match="Git-ignored ml/data"):
        initialize(tmp_path / "review.sqlite3", tmp_path / "queue.json", tmp_path / "processed.jsonl", IDENTITIES)
