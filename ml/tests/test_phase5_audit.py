"""Synthetic guard test; real audit is a separate aggregate-only command."""
import pytest

from ml.scripts.phase5_audit import audit


def test_auditor_rejects_artifacts_outside_ignored_data(tmp_path):
    with pytest.raises(ValueError, match="ml/data"):
        audit(tmp_path / "screening.jsonl", tmp_path / "plan.json")
