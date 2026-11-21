"""Offline, write-once human review of redacted OpenCity cases.

Only the local command-line interface displays case text. No sockets, telemetry or
model APIs are used. Reviewer credentials and decisions stay in ignored ml/data/.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ml.scripts.preprocess import file_digest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "opencity_ichangemycity_2019_2022"
DEFAULT_DB = ROOT / "data" / "reviews" / "opencity_phase4.sqlite3"
DEFAULT_QUEUE = ROOT / "data" / "evaluation" / "opencity_ichangemycity_2019_2022_phase3.stratified_review.json"
DEFAULT_PROCESSED = ROOT / "data" / "processed" / "opencity_ichangemycity_2019_2022_phase3.jsonl"
DEFAULT_SPLIT = ROOT / "data" / "evaluation" / "opencity_ichangemycity_2019_2022_phase3.split.json"
DEFAULT_SCREENING = ROOT / "data" / "phase5" / "screening_v3.jsonl"
ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")
ACTOR_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,31}$")
ALLOWED_NOTES = {"none", "needs_context", "label_ambiguous", "possible_indirect_identifier", "possible_template", "language_uncertain", "other_review_needed"}
AUTHORSHIP = {"citizen", "staff_note", "descriptor", "uncertain"}
TRISTATE = {"yes", "no", "uncertain"}
DISPOSITION = {"approve", "revise", "exclude", "escalate"}
LANGUAGES = {"english", "hindi", "hinglish", "kannada", "kannada_romanized", "code_mixed", "other", "unknown"}
ZERO_HASH = "0" * 64


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _secure_path(path: Path, owner_account: str | None = None, directory: bool = False) -> None:
    if os.name != "nt":
        path.chmod(0o700 if directory else 0o600)
        return
    domain = os.environ.get("USERDOMAIN", "")
    current = subprocess.run(["whoami"], check=True, capture_output=True, text=True).stdout.strip()
    accounts = {current}
    # In managed local sessions USERNAME can name the workspace owner while the
    # process token belongs to a sandbox account; preserve both explicitly.
    owner = os.environ.get("USERNAME") or getpass.getuser()
    accounts.add(f"{domain}\\{owner}" if domain else owner)
    if owner_account:
        accounts.add(owner_account)
    suffix = ":(OI)(CI)F" if directory else ":F"
    grants = [account + suffix for account in sorted(accounts)]
    grants.extend(["NT AUTHORITY\\SYSTEM" + suffix, "BUILTIN\\Administrators" + suffix])
    subprocess.run(["icacls", str(path), "/grant:r", *grants], check=True, capture_output=True)
    subprocess.run(["icacls", str(path), "/inheritance:r"], check=True, capture_output=True)


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError("Review store is not initialized")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _metadata(db: sqlite3.Connection) -> dict:
    return {row["name"]: row["value"] for row in db.execute("SELECT name,value FROM review_meta")}


def _verify_bound_files(db: sqlite3.Connection) -> tuple[Path, dict]:
    meta = _metadata(db)
    queue_path = Path(meta["queue_path"])
    processed_path = Path(meta["processed_path"])
    if (file_digest(queue_path) != meta["queue_sha256"] or file_digest(processed_path) != meta["processed_sha256"]
            or file_digest(Path(meta["split_path"])) != meta["split_sha256"]):
        raise ValueError("Review input changed after initialization; stop and investigate")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    return processed_path, queue


def _verify_chain(db: sqlite3.Connection) -> None:
    previous = ZERO_HASH
    expected_seq = 1
    for row in db.execute("SELECT * FROM review_events ORDER BY seq"):
        if row["seq"] != expected_seq or row["prev_hash"] != previous:
            raise ValueError("Review event sequence or hash chain is broken")
        actual = hashlib.sha256((previous + "\0" + str(row["seq"]) + "\0" + row["event_type"] + "\0" + row["record_id"] + "\0" + row["actor_id"] + "\0" + row["submitted_at_utc"] + "\0" + row["payload_json"]).encode("utf-8")).hexdigest()
        if actual != row["event_hash"]:
            raise ValueError("Review event hash mismatch")
        previous = actual
        expected_seq += 1


def _machine_assessments(db: sqlite3.Connection) -> dict[str, dict]:
    """Read only hash-bound local machine metadata; never treat it as a review."""
    if not DEFAULT_SCREENING.is_file():
        return {}
    manifest_path = DEFAULT_SCREENING.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise ValueError("Machine screening manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    meta = _metadata(db)
    if Path(meta["processed_path"]).resolve() != DEFAULT_PROCESSED.resolve():
        return {}
    if (manifest.get("output_sha256") != file_digest(DEFAULT_SCREENING)
            or manifest.get("input_sha256", {}).get("processed") != meta["processed_sha256"]
            or manifest.get("input_sha256", {}).get("split") != meta["split_sha256"]):
        raise ValueError("Machine screening input or output checksum changed")
    result = {}
    with DEFAULT_SCREENING.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                item = json.loads(line)
                record_id = item["record_id"]
                if not ID_PATTERN.fullmatch(record_id) or record_id in result or item.get("training_eligibility") is not False:
                    raise ValueError("Invalid machine screening metadata")
                result[record_id] = {key: item.get(key) for key in (
                    "machine_screening_status", "machine_privacy_risk", "privacy_evidence_codes",
                    "machine_authorship_suggestion", "authorship_evidence_codes",
                    "machine_category_suggestion", "category_evidence_codes",
                    "machine_language_suggestion", "quality_flags", "duplicate_candidate_ids",
                    "review_batch", "exclusion_recommended")}
    return result


def _authenticate(db: sqlite3.Connection, actor_id: str, passphrase: str, role: str) -> None:
    row = db.execute("SELECT role,salt,passphrase_hash FROM review_identities WHERE actor_id=?", (actor_id,)).fetchone()
    if row is None or row["role"] != role:
        raise PermissionError("Reviewer identity or role is invalid")
    candidate = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), bytes.fromhex(row["salt"]), 210_000)
    if not hmac.compare_digest(candidate, bytes.fromhex(row["passphrase_hash"])):
        raise PermissionError("Reviewer authentication failed")


def _validate_actor(actor_id: str, passphrase: str) -> None:
    if not ACTOR_PATTERN.fullmatch(actor_id):
        raise ValueError("Identity code must be 2-32 letters, digits, underscores or hyphens")
    if len(passphrase) < 15:
        raise ValueError("Reviewer passphrase must have at least 15 characters")


def initialize(db_path: Path, queue_path: Path, processed_path: Path, identities: dict[str, tuple[str, str]], *, split_path: Path = DEFAULT_SPLIT, owner_account: str | None = None, secure_permissions: bool = True) -> None:
    """Initialize once with exactly two reviewers and a distinct adjudicator."""
    db_path, queue_path, processed_path, split_path = map(Path, (db_path, queue_path, processed_path, split_path))
    if secure_permissions and not db_path.resolve().is_relative_to((ROOT / "data").resolve()):
        raise ValueError("Review decisions must be stored under Git-ignored ml/data")
    if db_path.exists():
        raise FileExistsError("Review store already exists; refusing to reset decisions")
    if sorted(role for role, _ in identities.values()) != ["adjudicator", "reviewer", "reviewer"]:
        raise ValueError("Exactly two reviewers and one distinct adjudicator are required")
    for actor_id, (_, passphrase) in identities.items():
        _validate_actor(actor_id, passphrase)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    ids = [item["record_id"] for item in queue["items"]]
    if not ids or len(ids) != len(set(ids)) or any(not ID_PATTERN.fullmatch(item) for item in ids):
        raise ValueError("Review queue IDs are missing, duplicated or malformed")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    assignment = {}
    for split_name, members in split["splits"].items():
        if split_name not in {"train", "validation", "test"}:
            raise ValueError("Unknown frozen split name")
        for record_id in members:
            if record_id in assignment:
                raise ValueError("Frozen split contains duplicate record ID")
            assignment[record_id] = split_name
    for item in queue["items"]:
        if item["record_id"] not in assignment or (item.get("split") and item["split"] != assignment[item["record_id"]]):
            raise ValueError("Queue ID or split differs from frozen split")
    source_ids = set()
    all_source_ids = set()
    with processed_path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if row["record_id"] in all_source_ids:
                    raise ValueError("Processed source contains duplicate record ID")
                all_source_ids.add(row["record_id"])
                if row.get("record_id") in ids:
                    if row.get("privacy_status") != "pending_human_review" or row.get("data_kind") != "real" or row.get("source_id") != SOURCE_ID:
                        raise ValueError("Queue includes a non-pending or non-OpenCity real record")
                    source_ids.add(row["record_id"])
    if source_ids != set(ids):
        raise ValueError("Review queue contains IDs absent from the processed source")
    if set(assignment) != all_source_ids:
        raise ValueError("Frozen split does not cover exactly the processed source")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if secure_permissions:
        _secure_path(db_path.parent, owner_account, directory=True)
    descriptor = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        if secure_permissions:
            _secure_path(db_path, owner_account)
        with _connect(db_path) as db:
            db.executescript("""
                CREATE TABLE review_meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE review_identities (actor_id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('reviewer','adjudicator')), salt TEXT NOT NULL, passphrase_hash TEXT NOT NULL);
                CREATE TABLE review_events (
                    seq INTEGER PRIMARY KEY, event_type TEXT NOT NULL CHECK(event_type IN ('review','adjudication')),
                    record_id TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES review_identities(actor_id),
                    submitted_at_utc TEXT NOT NULL, payload_json TEXT NOT NULL, prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE UNIQUE INDEX one_review_per_actor ON review_events(record_id,actor_id) WHERE event_type='review';
                CREATE UNIQUE INDEX one_adjudication_per_record ON review_events(record_id) WHERE event_type='adjudication';
                CREATE TRIGGER no_event_update BEFORE UPDATE ON review_events BEGIN SELECT RAISE(ABORT,'Review events are immutable'); END;
                CREATE TRIGGER no_event_delete BEFORE DELETE ON review_events BEGIN SELECT RAISE(ABORT,'Review events are immutable'); END;
                CREATE TRIGGER no_identity_update BEFORE UPDATE ON review_identities BEGIN SELECT RAISE(ABORT,'Review identities are immutable'); END;
                CREATE TRIGGER no_identity_delete BEFORE DELETE ON review_identities BEGIN SELECT RAISE(ABORT,'Review identities are immutable'); END;
            """)
            db.executemany("INSERT INTO review_meta(name,value) VALUES (?,?)", (
                ("queue_path", str(queue_path.resolve())), ("queue_sha256", file_digest(queue_path)),
                ("processed_path", str(processed_path.resolve())), ("processed_sha256", file_digest(processed_path)),
                ("split_path", str(split_path.resolve())), ("split_sha256", file_digest(split_path)),
                ("created_at_utc", datetime.now(timezone.utc).isoformat()),
            ))
            for actor_id, (role, passphrase) in identities.items():
                salt = os.urandom(16)
                digest = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 210_000)
                db.execute("INSERT INTO review_identities VALUES (?,?,?,?)", (actor_id, role, salt.hex(), digest.hex()))
    except Exception:
        db_path.unlink(missing_ok=True)
        raise


def _record(db: sqlite3.Connection, record_id: str) -> dict:
    if not ID_PATTERN.fullmatch(record_id):
        raise ValueError("Invalid hashed record ID")
    processed_path, queue = _verify_bound_files(db)
    if record_id not in {item["record_id"] for item in queue["items"]}:
        raise PermissionError("Record is outside the authorized review queue")
    with processed_path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if row.get("record_id") == record_id:
                    return row
    raise ValueError("Queued record missing from processed source")


def reviewer_case(db_path: Path, actor_id: str, passphrase: str, record_id: str) -> dict:
    """Expose only redacted source fields and this reviewer's own submission state."""
    with _connect(Path(db_path)) as db:
        db.execute("BEGIN")
        _authenticate(db, actor_id, passphrase, "reviewer")
        _verify_chain(db)
        row = _record(db, record_id)
        own = db.execute("SELECT payload_json FROM review_events WHERE event_type='review' AND record_id=? AND actor_id=?", (record_id, actor_id)).fetchone()
        machine = _machine_assessments(db).get(record_id)
        return {"record_id": record_id, "redacted_text": row["complaint_text"], "source_category": row.get("category"), "source_subcategory": row.get("source_subcategory"), "source_agency": row.get("source_agency"), "privacy_flags": row.get("privacy_flags", []), "script_hint": row.get("language"), "machine": machine, "own_submitted": own is not None}


def reviewer_progress(db_path: Path, actor_id: str, passphrase: str) -> dict:
    """Authenticated, own-work-only navigation over the bound local queue."""
    with _connect(Path(db_path)) as db:
        db.execute("BEGIN")
        _authenticate(db, actor_id, passphrase, "reviewer")
        _verify_chain(db)
        _, queue = _verify_bound_files(db)
        machine = _machine_assessments(db)
        own = {row["record_id"] for row in db.execute(
            "SELECT record_id FROM review_events WHERE event_type='review' AND actor_id=?", (actor_id,))}
        order = {"audit_30": 0, "high_privacy_or_exclusion": 1,
                 "ambiguous_quality_or_label": 2, "pilot_candidate": 3,
                 "representative_low_risk": 4}
        pending = [item["record_id"] for item in queue["items"] if item["record_id"] not in own]
        pending.sort(key=lambda record_id: (order.get((machine.get(record_id) or {}).get("review_batch"), 5), record_id))
        return {"total": len(queue["items"]), "submitted": len(own), "remaining": len(pending),
                "next_record_id": pending[0] if pending else None,
                "next_batch": (machine.get(pending[0]) or {}).get("review_batch") if pending else None}


def _agreement_summary(reviews: list[dict]) -> dict:
    if len(reviews) != 2:
        raise ValueError("Two reviews required for agreement summary")
    keys = ("authorship", "identifiers_remaining", "privacy_disposition", "category_correctness",
            "verified_language", "duplicate_status")
    first, second = (item["decision"] for item in reviews)
    return {"agree": [key for key in keys if first[key] == second[key]],
            "disagree": [key for key in keys if first[key] != second[key]]}


def _validate_notes(value) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 4 or any(note not in ALLOWED_NOTES for note in value):
        raise ValueError("Notes must be 1-4 approved reason codes; narrative text is forbidden")
    return sorted(set(value))


def validate_review(payload: dict) -> dict:
    allowed = {"authorship", "identifiers_remaining", "privacy_disposition", "category_correctness", "verified_language", "duplicate_status", "sanitized_notes"}
    if set(payload) != allowed:
        raise ValueError("Review fields are incomplete or unexpected")
    for name, options in (("authorship", AUTHORSHIP), ("identifiers_remaining", TRISTATE), ("privacy_disposition", DISPOSITION), ("category_correctness", TRISTATE), ("verified_language", LANGUAGES), ("duplicate_status", TRISTATE)):
        if payload[name] not in options:
            raise ValueError(f"Invalid {name}")
    if payload["privacy_disposition"] == "approve" and payload["identifiers_remaining"] != "no":
        raise ValueError("Privacy cannot be approved while identifiers remain or are uncertain")
    return {**payload, "sanitized_notes": _validate_notes(payload["sanitized_notes"])}


def _append(db: sqlite3.Connection, event_type: str, record_id: str, actor_id: str, payload: dict) -> None:
    row = db.execute("SELECT seq,event_hash FROM review_events ORDER BY seq DESC LIMIT 1").fetchone()
    seq = row["seq"] + 1 if row else 1
    previous = row["event_hash"] if row else ZERO_HASH
    submitted = datetime.now(timezone.utc).isoformat()
    payload_json = _json(payload)
    current = hashlib.sha256((previous + "\0" + str(seq) + "\0" + event_type + "\0" + record_id + "\0" + actor_id + "\0" + submitted + "\0" + payload_json).encode("utf-8")).hexdigest()
    db.execute("INSERT INTO review_events VALUES (?,?,?,?,?,?,?,?)", (seq, event_type, record_id, actor_id, submitted, payload_json, previous, current))


def submit_review(db_path: Path, actor_id: str, passphrase: str, record_id: str, payload: dict) -> None:
    payload = validate_review(payload)
    with _connect(Path(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        _authenticate(db, actor_id, passphrase, "reviewer")
        _verify_chain(db)
        _record(db, record_id)
        if db.execute("SELECT 1 FROM review_events WHERE event_type='adjudication' AND record_id=?", (record_id,)).fetchone():
            raise ValueError("Record is already adjudicated")
        _append(db, "review", record_id, actor_id, payload)


def _events(db: sqlite3.Connection, record_id: str, event_type: str) -> list[dict]:
    return [{"actor_id": row["actor_id"], "submitted_at_utc": row["submitted_at_utc"], "decision": json.loads(row["payload_json"]), "event_hash": row["event_hash"]} for row in db.execute("SELECT * FROM review_events WHERE record_id=? AND event_type=? ORDER BY seq", (record_id, event_type))]


def _status_from_db(db: sqlite3.Connection, record_id: str) -> dict:
    source = _record(db, record_id)
    reviews = _events(db, record_id, "review")
    adjudications = _events(db, record_id, "adjudication")
    state = "awaiting_reviews" if len(reviews) < 2 else "awaiting_adjudication"
    if adjudications:
        state = "adjudicated_" + {"approve": "approved", "revise": "revised", "exclude": "excluded", "escalate": "escalated"}[adjudications[0]["decision"]["final_disposition"]]
    if not adjudications:
        return {"record_id": record_id, "state": state, "review_count": len(reviews), "eligible": False,
                "training_eligibility": False, "human_reviewer_a_decision": None,
                "human_reviewer_b_decision": None, "human_adjudication": None,
                "reviews": [], "adjudication": None}
    final = adjudications[0]["decision"]
    safe_reviews = len(reviews) == 2 and len({item["actor_id"] for item in reviews}) == 2 and all(
        item["decision"]["authorship"] == "citizen"
        and item["decision"]["identifiers_remaining"] == "no"
        and item["decision"]["privacy_disposition"] == "approve"
        and item["decision"]["category_correctness"] == "yes"
        and item["decision"]["duplicate_status"] == "no"
        for item in reviews
    )
    eligible = (
        state == "adjudicated_approved" and safe_reviews
        and final["final_authorship"] == "citizen"
        and final["final_identifiers_remaining"] == "no"
        and final["final_category_correctness"] == "yes"
        and final["final_duplicate_status"] == "no"
        and final["final_language"] != "unknown"
        and bool(source.get("category"))
        and str(source["category"]).strip().upper() not in {"NULL", "N/A", "UNKNOWN"}
    )
    return {"record_id": record_id, "state": state, "review_count": len(reviews), "eligible": eligible,
            "training_eligibility": False,
            "human_reviewer_a_decision": reviews[0]["decision"],
            "human_reviewer_b_decision": reviews[1]["decision"],
            "human_adjudication": adjudications[0]["decision"],
            "reviews": reviews, "adjudication": adjudications[0]}


def review_status(db_path: Path, record_id: str, actor_id: str, passphrase: str) -> dict:
    """Authenticate before reading state; expose detailed evidence after adjudication."""
    with _connect(Path(db_path)) as db:
        db.execute("BEGIN")
        identity = db.execute("SELECT role FROM review_identities WHERE actor_id=?", (actor_id,)).fetchone()
        if identity is None:
            raise PermissionError("Reviewer identity is invalid")
        _authenticate(db, actor_id, passphrase, identity["role"])
        _verify_chain(db)
        return _status_from_db(db, record_id)


def export_manifest(db_path: Path, output_path: Path, actor_id: str, passphrase: str, *, secure_permissions: bool = True) -> str:
    """Write one protected, no-text snapshot covering every queued ID; refuse overwrite."""
    db_path, output_path = Path(db_path), Path(output_path)
    if output_path.parent.resolve() != db_path.parent.resolve() or output_path.suffix != ".json":
        raise ValueError("Evidence export must be a JSON file beside the protected review database")
    if output_path.exists():
        raise FileExistsError("Evidence snapshot exists; refusing overwrite")
    with _connect(db_path) as db:
        _authenticate(db, actor_id, passphrase, "adjudicator")
        db.execute("BEGIN IMMEDIATE")
        _verify_chain(db)
        _, queue = _verify_bound_files(db)
        meta = _metadata(db)
        rows = []
        for item in queue["items"]:
            row = _status_from_db(db, item["record_id"])
            row["reviews"] = _events(db, item["record_id"], "review")
            rows.append(row)
        head = db.execute("SELECT event_hash FROM review_events ORDER BY seq DESC LIMIT 1").fetchone()
        snapshot = {
            "schema": "nagrikos.phase4.review_manifest.v1",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "queue_sha256": meta["queue_sha256"],
            "processed_sha256": meta["processed_sha256"],
            "split_sha256": meta["split_sha256"],
            "event_chain_head": head["event_hash"] if head else ZERO_HASH,
            "record_count": len(rows),
            "records": rows,
        }
    encoded = (_json(snapshot) + "\n").encode("utf-8")
    descriptor = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            if secure_permissions:
                _secure_path(output_path)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor != -1:
            os.close(descriptor)
        output_path.unlink(missing_ok=True)
        raise
    return hashlib.sha256(encoded).hexdigest()


def adjudication_material(db_path: Path, actor_id: str, passphrase: str, record_id: str) -> dict:
    """Allow the appointed adjudicator to read both decisions after both exist."""
    with _connect(Path(db_path)) as db:
        db.execute("BEGIN")
        _authenticate(db, actor_id, passphrase, "adjudicator")
        _verify_chain(db)
        row = _record(db, record_id)
        reviews = _events(db, record_id, "review")
        if len(reviews) != 2:
            raise ValueError("Two independent reviews are required before adjudication")
        return {"record_id": record_id, "redacted_text": row["complaint_text"], "source_category": row.get("category"), "source_subcategory": row.get("source_subcategory"), "privacy_flags": row.get("privacy_flags", []), "reviews": reviews, "agreement_summary": _agreement_summary(reviews), "machine": _machine_assessments(db).get(record_id)}


def submit_adjudication(db_path: Path, actor_id: str, passphrase: str, record_id: str, payload: dict) -> None:
    allowed = {"final_disposition", "final_authorship", "final_identifiers_remaining", "final_category_correctness", "final_language", "final_duplicate_status", "sanitized_notes"}
    if set(payload) != allowed:
        raise ValueError("Adjudication fields are incomplete or unexpected")
    for name, options in (("final_disposition", DISPOSITION), ("final_authorship", AUTHORSHIP), ("final_identifiers_remaining", TRISTATE), ("final_category_correctness", TRISTATE), ("final_language", LANGUAGES), ("final_duplicate_status", TRISTATE)):
        if payload[name] not in options:
            raise ValueError(f"Invalid {name}")
    payload = {**payload, "sanitized_notes": _validate_notes(payload["sanitized_notes"])}
    with _connect(Path(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        _authenticate(db, actor_id, passphrase, "adjudicator")
        _verify_chain(db)
        source = _record(db, record_id)
        reviews = _events(db, record_id, "review")
        if len(reviews) != 2 or len({item["actor_id"] for item in reviews}) != 2 or actor_id in {item["actor_id"] for item in reviews}:
            raise ValueError("Two independent reviewers must submit before adjudication")
        if payload["final_disposition"] == "approve":
            if not source.get("category") or str(source["category"]).strip().upper() in {"NULL", "N/A", "UNKNOWN"}:
                raise ValueError("Approval requires a meaningful original source category")
            if not all(item["decision"]["privacy_disposition"] == "approve" and item["decision"]["identifiers_remaining"] == "no" and item["decision"]["authorship"] == "citizen" and item["decision"]["category_correctness"] == "yes" and item["decision"]["duplicate_status"] == "no" for item in reviews):
                raise ValueError("Approval requires two agreeing privacy-safe citizen/category reviews")
            if payload["final_identifiers_remaining"] != "no" or payload["final_authorship"] != "citizen" or payload["final_category_correctness"] != "yes" or payload["final_duplicate_status"] != "no" or payload["final_language"] == "unknown":
                raise ValueError("Approval requires explicit safe authorship, category and verified language")
        _append(db, "adjudication", record_id, actor_id, payload)


def _prompt_choice(label: str, choices: set[str]) -> str:
    options = "/".join(sorted(choices))
    while True:
        response = input(f"{label} ({options}): ").strip().lower()
        if response in choices:
            return response
        print("Choose one of the listed values.")


def _prompt_notes() -> list[str]:
    print("Notes are controlled reason codes only; do not enter names, locations or text excerpts.")
    print("Codes: " + ", ".join(sorted(ALLOWED_NOTES)))
    while True:
        raw = input("Note codes, comma-separated [none]: ").strip().lower() or "none"
        try:
            return _validate_notes([part.strip() for part in raw.split(",")])
        except ValueError as exc:
            print(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Coordinator: initialize once; passphrases are prompted, not stored in shell history")
    init.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    init.add_argument("--processed", type=Path, default=DEFAULT_PROCESSED)
    init.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    init.add_argument("--reviewer-a", required=True)
    init.add_argument("--reviewer-b", required=True)
    init.add_argument("--adjudicator", required=True)
    init.add_argument("--owner-account", help="Optional additional local OS account allowed to read review store")
    show = commands.add_parser("show", help="Reviewer: show one redacted record, without peer decisions")
    show.add_argument("--reviewer", required=True)
    show.add_argument("--record-id", required=True)
    review = commands.add_parser("review", help="Reviewer: submit one write-once structured decision")
    review.add_argument("--reviewer", required=True)
    review.add_argument("--record-id", required=True)
    adjudicate = commands.add_parser("adjudicate", help="Independent adjudicator: resolve after two reviews")
    adjudicate.add_argument("--adjudicator", required=True)
    adjudicate.add_argument("--record-id", required=True)
    status = commands.add_parser("status", help="Show aggregate state without case text or decisions")
    status.add_argument("--record-id", required=True)
    status.add_argument("--actor", required=True)
    progress = commands.add_parser("progress", help="Reviewer: own progress and next prioritized hashed ID")
    progress.add_argument("--reviewer", required=True)
    export = commands.add_parser("export", help="Adjudicator: write one no-text evidence snapshot beside review DB")
    export.add_argument("--adjudicator", required=True)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init":
        codes = [args.reviewer_a, args.reviewer_b, args.adjudicator]
        if len(set(codes)) != 3:
            parser.error("Reviewer and adjudicator codes must all be different")
        identities = {code: ("adjudicator" if code == args.adjudicator else "reviewer", getpass.getpass(f"Passphrase for {code}: ")) for code in codes}
        initialize(args.db, args.queue, args.processed, identities, split_path=args.split, owner_account=args.owner_account)
        print("Review store initialized; no decisions or approvals recorded.")
        return
    if args.command == "status":
        result = review_status(args.db, args.record_id, args.actor, getpass.getpass("Reviewer passphrase: "))
        print(json.dumps({"record_id": result["record_id"], "state": result["state"], "review_count": result["review_count"], "adjudicated": result["adjudication"] is not None}))
        return
    if args.command == "progress":
        result = reviewer_progress(args.db, args.reviewer, getpass.getpass("Reviewer passphrase: "))
        print(json.dumps(result, sort_keys=True))
        return
    if args.command == "export":
        digest = export_manifest(args.db, args.output, args.adjudicator, getpass.getpass("Adjudicator passphrase: "))
        print(json.dumps({"snapshot": str(args.output), "sha256": digest}))
        return
    actor = args.adjudicator if args.command == "adjudicate" else args.reviewer
    secret = getpass.getpass("Reviewer passphrase: ")
    if args.command in ("show", "review"):
        case = reviewer_case(args.db, actor, secret, args.record_id)
        print("\nRecord:", case["record_id"])
        print("Source category:", case["source_category"])
        print("Source subcategory:", case["source_subcategory"])
        print("Source agency:", case["source_agency"])
        print("Privacy flags:", ", ".join(case["privacy_flags"]) or "none")
        print("Script hint:", case["script_hint"])
        if case["machine"]:
            print("Machine triage (unverified):", json.dumps(case["machine"], sort_keys=True))
        print("Redacted text:\n", case["redacted_text"])
        print("Your decision already submitted:", case["own_submitted"])
        if args.command == "show":
            return
        payload = {
            "authorship": _prompt_choice("Authorship", AUTHORSHIP),
            "identifiers_remaining": _prompt_choice("Identifiers remaining", TRISTATE),
            "privacy_disposition": _prompt_choice("Privacy disposition", DISPOSITION),
            "category_correctness": _prompt_choice("Original source category correct", TRISTATE),
            "verified_language": _prompt_choice("Verified language", LANGUAGES),
            "duplicate_status": _prompt_choice("Duplicate/template suspected", TRISTATE),
            "sanitized_notes": _prompt_notes(),
        }
        submit_review(args.db, actor, secret, args.record_id, payload)
        print("Decision recorded. Peer decisions remain hidden; explicit adjudication is required.")
        return
    result = adjudication_material(args.db, actor, secret, args.record_id)
    print("Record:", result["record_id"])
    print("Source category:", result["source_category"])
    print("Source subcategory:", result["source_subcategory"])
    print("Privacy flags:", ", ".join(result["privacy_flags"]) or "none")
    if result["machine"]:
        print("Machine triage (unverified):", json.dumps(result["machine"], sort_keys=True))
    print("Reviewer agreement by field:", json.dumps(result["agreement_summary"], sort_keys=True))
    print("Redacted text:\n", result["redacted_text"])
    print(json.dumps({"reviews": result["reviews"]}, indent=2))
    payload = {
        "final_disposition": _prompt_choice("Final disposition", DISPOSITION),
        "final_authorship": _prompt_choice("Final authorship", AUTHORSHIP),
        "final_identifiers_remaining": _prompt_choice("Final identifiers remaining", TRISTATE),
        "final_category_correctness": _prompt_choice("Final source category correct", TRISTATE),
        "final_language": _prompt_choice("Final verified language", LANGUAGES),
        "final_duplicate_status": _prompt_choice("Final duplicate/template status", TRISTATE),
        "sanitized_notes": _prompt_notes(),
    }
    submit_adjudication(args.db, actor, secret, args.record_id, payload)
    print("Explicit human adjudication recorded; eligibility is decided by the separate gate.")


if __name__ == "__main__":
    main()
