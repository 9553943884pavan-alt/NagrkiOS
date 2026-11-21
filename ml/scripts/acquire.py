"""Download only audited, approved public data with an immutable provenance record.

Usage: python ml/scripts/acquire.py --source nyc_311_2024_bounded
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "sources.json"
DEFAULT_DATA = ROOT / "data"
CHUNK = 65536
MAX_BYTES = 10_000_000
MAX_RETRIES = 3


def _safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", value):
        raise ValueError("Source id must be lowercase letters, digits and underscores")
    return value


def _validate_source(source: dict) -> None:
    _safe_id(source["id"])
    if source.get("status") != "approved" or source.get("approved_for_download") is not True:
        raise ValueError(f"Source {source['id']} is not approved for acquisition")
    url = urlparse(source["url"])
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise ValueError("Approved source requires an HTTPS URL without embedded credentials")
    if source.get("format") not in ("json", "jsonl", "csv"):
        raise ValueError("Source format must be json, jsonl, or csv")
    if not source.get("license") or not (source.get("license_evidence_url") or source.get("evidence_url")):
        raise ValueError("Approved source requires license and evidence URL")
    limit = source.get("max_bytes", MAX_BYTES)
    if not isinstance(limit, int) or limit <= 0 or limit > 100_000_000:
        raise ValueError("Invalid download byte limit")


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _row_count(path: Path, format_name: str) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        if format_name == "csv":
            return max(0, sum(1 for _ in csv.reader(stream)) - 1)
        if format_name == "jsonl":
            return sum(bool(line.strip()) for line in stream)
        data = json.load(stream)
        if not isinstance(data, list):
            raise ValueError("JSON source must contain an array of records")
        return len(data)


def _retry_delay(headers, attempt: int) -> float:
    value = headers.get("Retry-After") if headers else None
    if value:
        try:
            return min(30.0, max(0.0, float(value)))
        except ValueError:
            try:
                return min(30.0, max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
            except (ValueError, TypeError):
                pass
    return min(8.0, 2.0**attempt)


def acquire(source: dict, data_root: Path = DEFAULT_DATA, *, opener=urlopen, sleeper=time.sleep) -> dict:
    """Acquire a source or verify and reuse its existing immutable download."""
    _validate_source(source)
    source_id = source["id"]
    data_root = Path(data_root)
    manifest_path = data_root / "manifests" / f"{source_id}.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw = data_root / existing["path"]
        if raw.is_file() and raw.stat().st_size == existing["bytes"] and _sha256(raw) == existing["sha256"]:
            if existing.get("source_url") == source["url"] and existing.get("status") == "verified":
                return existing

    destination = data_root / "raw" / source_id
    destination.mkdir(parents=True, exist_ok=True)
    # Include the URL fingerprint so a changed source query cannot resume old bytes.
    partial = destination / f"download-{hashlib.sha256(source['url'].encode('utf-8')).hexdigest()[:16]}.part"
    limit = source.get("max_bytes", MAX_BYTES)
    for attempt in range(MAX_RETRIES + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > limit:
            raise ValueError("Existing partial download exceeds source byte limit")
        headers = {"User-Agent": "NagrikOS-ML-data-research/1.0", "Accept": "application/json,text/csv,*/*"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(source["url"], headers=headers)
        try:
            with opener(request, timeout=30) as response:
                final_url = urlparse(response.geturl())
                if final_url.scheme != "https":
                    raise ValueError("Source redirected away from HTTPS")
                status = response.status
                if status not in (200, 206):
                    raise ValueError(f"Unexpected HTTP status {status}")
                if status == 206 and not offset:
                    raise ValueError("Server returned a partial response without a resume request")
                if offset and status == 206:
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise ValueError("Server returned a mismatched resume range")
                if offset and status == 200:
                    offset = 0  # Server ignored Range; restart instead of appending.
                with partial.open("ab" if offset else "wb") as stream:
                    total = offset
                    for chunk in iter(lambda: response.read(CHUNK), b""):
                        total += len(chunk)
                        if total > limit:
                            raise ValueError("Download exceeded configured byte limit")
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            break
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == MAX_RETRIES:
                raise RuntimeError(f"Source returned HTTP {exc.code}") from exc
            sleeper(_retry_delay(exc.headers, attempt))
        except (URLError, TimeoutError, ConnectionError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError("Source download failed after retries") from exc
            sleeper(_retry_delay(None, attempt))
        except ValueError:
            partial.unlink(missing_ok=True)
            raise

    try:
        rows = _row_count(partial, source["format"])
        if source.get("max_records") is not None and rows > source["max_records"]:
            raise ValueError("Download exceeded configured record limit")
        checksum = _sha256(partial)
        immutable = destination / f"{checksum}.{source['format']}"
        if immutable.exists():
            if immutable.stat().st_size != partial.stat().st_size or _sha256(immutable) != checksum:
                raise ValueError("Existing immutable file failed integrity check")
            partial.unlink()
        else:
            os.replace(partial, immutable)
        manifest = {
            "source_id": source_id,
            "source_url": source["url"],
            "license": source["license"],
            "evidence_url": source.get("license_evidence_url") or source.get("evidence_url"),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "path": immutable.relative_to(data_root).as_posix(),
            "sha256": checksum,
            "bytes": immutable.stat().st_size,
            "row_count": rows,
            "format": source["format"],
            "status": "verified",
            "sampling_method": source.get("sampling_method"),
        }
        _atomic_json(manifest_path, manifest)
        return manifest
    except (UnicodeError, json.JSONDecodeError, csv.Error, ValueError):
        # Invalid content cannot be resumed safely; never publish its manifest.
        partial.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Approved source id from sources.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    source = next((s for s in config["sources"] if s["id"] == args.source), None)
    if source is None:
        parser.error("Unknown source id")
    result = acquire(source, args.data_root)
    print(json.dumps({key: result[key] for key in ("source_id", "path", "sha256", "bytes", "row_count", "status")}))


if __name__ == "__main__":
    main()
