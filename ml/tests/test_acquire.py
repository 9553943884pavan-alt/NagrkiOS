"""Acquisition tests use in-memory HTTPS responses; no live network calls."""

import io
import json
import hashlib
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from acquire import acquire  # noqa: E402


SOURCE = {
    "id": "sample_source",
    "url": "https://data.example.org/sample.json",
    "status": "approved",
    "approved_for_download": True,
    "format": "json",
    "license": "CC0",
    "evidence_url": "https://data.example.org/license",
    "max_bytes": 1000,
}


def partial_path(root):
    fingerprint = hashlib.sha256(SOURCE["url"].encode("utf-8")).hexdigest()[:16]
    return root / "raw/sample_source" / f"download-{fingerprint}.part"


class Response(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, headers=None, url=SOURCE["url"]):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}
        self.url = url

    def geturl(self):
        return self.url


def test_acquires_with_checksum_and_reuses_verified_file(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        return Response(b'[{"a": 1}, {"a": 2}]')

    first = acquire(SOURCE, tmp_path, opener=opener)
    assert first["row_count"] == 2
    assert first["status"] == "verified"
    assert first["source_id"] == SOURCE["id"]
    assert first["bytes"] == len(b'[{"a": 1}, {"a": 2}]')
    assert len(first["sha256"]) == 64
    assert (tmp_path / first["path"]).exists()
    assert json.loads((tmp_path / "manifests/sample_source.json").read_text()) == first
    second = acquire(SOURCE, tmp_path, opener=opener)
    assert first == second
    assert len(calls) == 1


def test_rejects_unapproved_or_unlicensed_sources(tmp_path):
    with pytest.raises(ValueError, match="not approved"):
        acquire({**SOURCE, "status": "conditional"}, tmp_path)
    with pytest.raises(ValueError, match="not approved"):
        acquire({key: value for key, value in SOURCE.items() if key != "approved_for_download"}, tmp_path)
    with pytest.raises(ValueError, match="license"):
        acquire({**SOURCE, "license": ""}, tmp_path)
    with pytest.raises(ValueError, match="HTTPS"):
        acquire({**SOURCE, "url": "http://data.example.org/sample.json"}, tmp_path)


def test_resume_uses_range_and_validates_content_range(tmp_path):
    part = partial_path(tmp_path)
    part.parent.mkdir(parents=True)
    part.write_bytes(b'[{"a":')

    def opener(request, timeout):
        assert request.get_header("Range") == "bytes=6-"
        return Response(b" 1}]", status=206, headers={"Content-Range": "bytes 6-9/10"})

    result = acquire(SOURCE, tmp_path, opener=opener)
    assert result["row_count"] == 1
    assert (tmp_path / result["path"]).read_bytes() == b'[{"a": 1}]'


def test_rejects_mismatched_resume_range(tmp_path):
    part = partial_path(tmp_path)
    part.parent.mkdir(parents=True)
    part.write_bytes(b"[")

    def opener(request, timeout):
        return Response(b"[]", status=206, headers={"Content-Range": "bytes 2-3/4"})

    with pytest.raises(ValueError, match="mismatched"):
        acquire(SOURCE, tmp_path, opener=opener)
    assert not (tmp_path / "manifests/sample_source.json").exists()


def test_retries_transient_status_and_failure_never_publishes_manifest(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(1)
        raise HTTPError(SOURCE["url"], 429, "rate limited", {"Retry-After": "0"}, None)

    with pytest.raises(RuntimeError, match="HTTP 429"):
        acquire(SOURCE, tmp_path, opener=opener, sleeper=lambda _: None)
    assert len(calls) == 4
    assert not (tmp_path / "manifests/sample_source.json").exists()


def test_retries_network_failure_then_succeeds(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise URLError("unavailable")
        return Response(b"[]")

    assert acquire(SOURCE, tmp_path, opener=opener, sleeper=lambda _: None)["row_count"] == 0
    assert len(calls) == 2


def test_byte_limit_and_invalid_json_never_publish_manifest(tmp_path):
    for body in (b" " * 1001, b"{bad json}"):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            acquire(SOURCE, tmp_path, opener=lambda request, timeout: Response(body))
        assert not (tmp_path / "manifests/sample_source.json").exists()
        assert not partial_path(tmp_path).exists()
