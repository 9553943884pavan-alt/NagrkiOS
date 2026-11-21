"""Synthetic fixtures only; no OpenCity narratives enter test output."""
import pytest

from ml.scripts.phase5_screen import GARBAGE, ROAD, assess, write_results


def test_machine_assessment_never_claims_human_clearance():
    result = assess("Please repair the road near my school. We are facing potholes.", [], ROAD)
    assert result["machine_screening_status"] == "screened"
    assert result["machine_privacy_risk"] in {"high", "uncertain", "low"}
    assert result["machine_language_suggestion"]["provenance"] == "machine_predicted"
    assert not any(name.startswith("human_") for name in result)


def test_direct_and_combined_indirect_risks():
    direct = assess("Please call me on 9876543210 about the garbage issue.", [], GARBAGE)
    assert direct["machine_privacy_risk"] == "high"
    assert direct["redaction_recommended"]
    indirect = assess("My family lives behind the school and faces road damage.", [], ROAD)
    assert indirect["machine_privacy_risk"] == "high"
    assert "household_context" in indirect["privacy_evidence_codes"]
    assert "possible_indirect_location" in indirect["privacy_evidence_codes"]


def test_missing_label_and_short_text_are_not_approved():
    result = assess("bad", [], None)
    assert result["machine_authorship_suggestion"] == "uncertain"
    assert result["exclusion_recommended"]
    assert "missing_source_category" in result["category_evidence_codes"]


def test_output_path_must_be_ignored_data_area(tmp_path):
    with pytest.raises(ValueError, match="ignored ml/data"):
        write_results(tmp_path / "public.jsonl")
