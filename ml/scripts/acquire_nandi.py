"""Collect a bounded, stratified synthetic Nandi subset from Hugging Face's public viewer.

No model training. Only minimal source fields are retained; output is ignored by Git.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ml.scripts.preprocess import file_digest, normalize, redact

ROOT = Path(__file__).resolve().parents[1]
DATASET = "LatentAILabs/nandi-grievance-synthetic"
REVISION = "cf76fd674a7bf03c770a92eaca0e81825cb949fc"
LICENSE = "Apache-2.0"
OFFSETS = (0, 14500, 29000, 43500, 58000, 72500, 87000, 101500, 116000)
LENGTH = 100
LANGUAGES = ("hi", "hinglish", "en")
QUOTAS = {"gov": 20, "none": 10, "other": 20}
MAX_RESPONSE_BYTES = 1_000_000
MAX_RETRIES = 3
ALLOWED_HOSTS = {"huggingface.co", "datasets-server.huggingface.co"}


def source_urls() -> list[str]:
    base = "https://datasets-server.huggingface.co/rows"
    return [base + "?" + urlencode({"dataset": DATASET, "config": "default", "split": "train", "offset": offset, "length": LENGTH}) for offset in OFFSETS]


def fetch_json(url: str, *, opener=urlopen, sleeper=time.sleep) -> dict:
    from urllib.parse import urlparse
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED_HOSTS:
        raise ValueError("Only allowlisted HTTPS Hugging Face endpoints may be queried")
    request = Request(url, headers={"User-Agent": "NagrikOS-ML-data-research/2.0", "Accept": "application/json"})
    for attempt in range(MAX_RETRIES + 1):
        try:
            with opener(request, timeout=30) as response:
                final = urlparse(response.geturl())
                if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
                    raise ValueError("Unexpected redirect destination")
                if response.status != 200:
                    raise ValueError(f"Unexpected HTTP status {response.status}")
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("Viewer response exceeded byte limit")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise ValueError("Viewer response must be a JSON object")
                return result
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == MAX_RETRIES:
                raise RuntimeError(f"Hugging Face returned HTTP {exc.code}") from exc
            sleeper(min(8, 2**attempt))
        except (URLError, TimeoutError, ConnectionError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError("Hugging Face request failed after retries") from exc
            sleeper(min(8, 2**attempt))
    raise AssertionError("retry loop exhausted")


def select(rows: list[dict]) -> tuple[list[dict], dict]:
    """Deterministic language/domain quotas across systematic source row slices."""
    by_id = {}
    for wrapper in rows:
        row = wrapper.get("row", {})
        if row.get("language") in LANGUAGES and isinstance(row.get("text"), str) and row.get("id") and row.get("category"):
            by_id[str(row["id"])] = row
    pools: dict[tuple[str, str], list[dict]] = {}
    for row in by_id.values():
        domain = row.get("domain")
        bucket = "gov" if domain == "gov" else "none" if domain == "none" else "other"
        pools.setdefault((row["language"], bucket), []).append(row)
    chosen = []
    shortages = {}
    for language in LANGUAGES:
        for bucket, quota in QUOTAS.items():
            candidates = sorted(pools.get((language, bucket), []), key=lambda row: hashlib.sha256(("nandi-phase2-v1\0" + str(row["id"])).encode()).hexdigest())
            selected = candidates[:quota]
            chosen.extend(selected)
            if len(selected) < quota:
                shortages[f"{language}:{bucket}"] = quota - len(selected)
    # IDs have been deduplicated above. Keep deterministic output order.
    chosen.sort(key=lambda row: (row["language"], str(row["id"])))
    return chosen, {"candidate_count": len(by_id), "shortages": shortages, "language_counts": dict(Counter(row["language"] for row in chosen)), "domain_counts": dict(Counter(row["domain"] for row in chosen))}


def transform(row: dict) -> tuple[dict, dict]:
    required = ("id", "text", "category", "domain", "urgency", "language")
    if any(not row.get(key) for key in required):
        raise ValueError("Selected source row lacks required fields")
    if row["language"] not in LANGUAGES or row["urgency"] not in ("P1", "P2", "P3"):
        raise ValueError("Unexpected source language or urgency label")
    source_id = str(row["id"])
    text = normalize(row["text"])
    cleaned, signals = redact(text)
    raw = {key: row[key] for key in required}
    raw["data_kind"] = "synthetic"
    prepared = {
        "record_id": hashlib.sha256((DATASET + "\0" + source_id).encode()).hexdigest(),
        "source_id": "nandi_synthetic_phase2",
        "data_kind": "synthetic",
        "complaint_text": cleaned,
        "text_kind": "synthetic_narrative",
        "language": row["language"],
        "category": row["category"],
        "category_source": "synthetic_generated",
        "department": None,
        "source_domain": row["domain"],
        "urgency": row["urgency"],
        "urgency_source": "synthetic_generated",
        "location": None,
        "created_at": None,
        "closed_at": None,
        "status": None,
        "privacy_review_required": True,
    }
    if not cleaned:
        raise ValueError("Empty selected text")
    return raw, prepared


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def acquire(data_root: Path = ROOT / "data", *, fetch=fetch_json) -> dict:
    manifest_path = data_root / "manifests" / "nandi_synthetic_phase2.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_path = data_root / manifest["raw_path"]
        processed_path = data_root / manifest["processed_path"]
        if (manifest.get("dataset_revision") == REVISION and raw_path.exists() and processed_path.exists()
                and file_digest(raw_path) == manifest["raw_sha256"] and file_digest(processed_path) == manifest["processed_sha256"]):
            return manifest
        raise ValueError("Existing Nandi manifest or file failed integrity check")
    metadata_url = "https://huggingface.co/api/datasets/" + DATASET
    metadata = fetch(metadata_url)
    if metadata.get("sha") != REVISION or metadata.get("private") or metadata.get("gated") not in (False, None):
        raise ValueError("Dataset revision or public access changed; review before collecting")
    if "license:apache-2.0" not in metadata.get("tags", []):
        raise ValueError("Apache-2.0 license tag missing; review before collecting")
    wrappers = []
    page_counts = {}
    for offset, url in zip(OFFSETS, source_urls()):
        response = fetch(url)
        if response.get("partial") or response.get("num_rows_total") != 116199:
            raise ValueError("Dataset viewer reports partial or changed train split")
        page = response.get("rows")
        if not isinstance(page, list) or len(page) != LENGTH:
            raise ValueError("Unexpected viewer page size")
        wrappers.extend(page)
        page_counts[str(offset)] = len(page)
    if fetch(metadata_url).get("sha") != REVISION:
        raise ValueError("Dataset revision changed during collection")
    selected, selection = select(wrappers)
    if not selected:
        raise ValueError("No rows selected")
    raw_rows, prepared_rows = [], []
    for row in selected:
        raw, prepared = transform(row)
        raw_rows.append(raw)
        prepared_rows.append(prepared)
    raw_path = data_root / "raw" / "nandi_synthetic_phase2" / "selected.jsonl"
    processed_path = data_root / "processed" / "nandi_synthetic_phase2.jsonl"
    if raw_path.exists() or processed_path.exists():
        raise FileExistsError("Unmanifested Nandi output exists; inspect before retrying")
    write_jsonl(raw_path, raw_rows)
    write_jsonl(processed_path, prepared_rows)
    manifest = {
        "source_id": "nandi_synthetic_phase2",
        "data_kind": "synthetic",
        "dataset_url": "https://huggingface.co/datasets/" + DATASET,
        "dataset_revision": REVISION,
        "license": LICENSE,
        "license_evidence_url": "https://huggingface.co/datasets/" + DATASET,
        "collection_method": "Hugging Face dataset viewer /rows, systematic offsets then deterministic language/domain quotas",
        "offsets": list(OFFSETS),
        "page_counts": page_counts,
        "selected_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_path": raw_path.relative_to(data_root).as_posix(),
        "processed_path": processed_path.relative_to(data_root).as_posix(),
        "raw_sha256": file_digest(raw_path),
        "processed_sha256": file_digest(processed_path),
        "row_count": len(prepared_rows),
        "selection": selection,
        "generated_labels_only": True,
        "human_reviewed_labels": 0,
        "limitations": ["Synthetic LLM-generated text and labels; no real complaint ground truth", "Urgency labels are experimental and not safety ground truth", "A bounded systematic sample is not representative of all categories or Indian civic complaints"],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(".partial")
    try:
        temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


if __name__ == "__main__":
    result = acquire()
    print(json.dumps({key: result[key] for key in ("source_id", "data_kind", "row_count", "raw_sha256", "processed_sha256", "dataset_revision")}, sort_keys=True))
