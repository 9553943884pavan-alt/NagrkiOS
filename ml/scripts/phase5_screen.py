"""Offline, deterministic triage of the frozen OpenCity collection.

Writes case-level metadata only to ignored, restricted ml/data/phase5. Never
prints source text, IDs, or case-level assessments. Rules are triage, not labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from ml.scripts.preprocess import file_digest
from ml.scripts.privacy_scan import PATTERNS
from ml.scripts.review_local import _secure_path
from ml.scripts.split import canonical

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed/opencity_ichangemycity_2019_2022_phase3.jsonl"
MANIFEST = DATA / "manifests/opencity_ichangemycity_2019_2022_phase3.json"
SPLIT = DATA / "evaluation/opencity_ichangemycity_2019_2022_phase3.split.json"
QUEUE = DATA / "evaluation/opencity_ichangemycity_2019_2022_phase3.stratified_review.json"
MINIMAL = DATA / "raw/opencity_ichangemycity_2019_2022/field_minimized_redacted.jsonl"
OUTPUT = DATA / "phase5/screening_v3.jsonl"
PLAN = DATA / "phase5/review_plan_v3.json"
EXPECTED = {
    "processed": "a9e2306b635e7b6d554c314893e016b3349619d853cb857db99b035bb51f2ccd",
    "split": "c58aa51f60bf174b3262694ab2153ce22398d70bef2713607b0d1603a18c24f0",
    "queue": "6a6e7875d8d057316f994b8fb8353b168f54d60ed7e2461844ed353376a6ab32",
    "manifest": "86cb84ac1632cfe244fdfb497c19754b38ad6f5c3e262745fb33d9a90ba07f85",
}
RULESET = "phase5-deterministic-v3"
ROAD = "Mobility - Roads, Footpaths and Infrastructure"
GARBAGE = "Garbage and Unsanitary Practices"

WORD = lambda value: re.compile(r"(?i)\b(?:" + value + r")\b")
PLACE = WORD("near|opposite|behind|beside|adjacent|landmark|ward|village|colony|lane|cross|main road|house|home|apartment|school|hospital|temple|mosque|church|station|bus stop")
HOUSEHOLD = WORD("family|wife|husband|daughter|son|mother|father|elderly|child|tenant|landlord|household")
NAME_CUE = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt|Sri)\.?\s+[A-Z][a-z]{2,}\b")
UNUSUAL_NUMBER = re.compile(r"(?<!\w)(?:\d[\s-]){3,}\d(?!\w)|(?<!\d)\d{4,5}(?!\d)")
SPEAKER = WORD("i|we|my|our|us|complain|request|please|facing|suffering|need|kindly")
STAFF = WORD("inspected|forwarded|assigned|closed by|resolved by|field officer|staff note|as per inspection|action taken")
CORRUPT = re.compile(r"\ufffd|(?:\?){4,}|(?:[^\w\s.,;:!?()\[\]'-]){8,}")
ROAD_TERMS = WORD("road|roadway|pothole|footpath|sidewalk|pavement|asphalt|street|traffic|junction")
GARBAGE_TERMS = WORD("garbage|rubbish|waste|trash|dump|litter|unclean|sanitation|bin|collection")
DEVANAGARI = re.compile(r"[\u0900-\u097f]")
KANNADA = re.compile(r"[\u0c80-\u0cff]")
LATIN = re.compile(r"[A-Za-z]")
ENGLISH_HINT = WORD("the|is|are|and|have|has|this|that|please|road|garbage")
HINGLISH_HINT = WORD("hai|nahi|kya|bahut|pani|sadak|kachra|karna|gali|safai")


def assess(text: str, existing_flags: list[str], source_category: str | None) -> dict:
    """Pure rules. All assessments are provisional and may miss identifiers."""
    privacy = set(existing_flags)
    privacy.update(name for name, pattern in PATTERNS.items() if pattern.search(text))
    if NAME_CUE.search(text):
        privacy.add("possible_person_name")
    if PLACE.search(text):
        privacy.add("possible_indirect_location")
    if HOUSEHOLD.search(text):
        privacy.add("household_context")
    if UNUSUAL_NUMBER.search(text):
        privacy.add("unusual_number")
    direct = bool(privacy & set(PATTERNS))
    indirect = len(privacy & {"possible_person_name", "possible_indirect_location", "household_context", "unusual_number", "possible_name", "possible_location"})
    risk = "high" if direct or indirect >= 2 else "uncertain" if privacy else "low"
    # Low means no *detected* risk; it is never an anonymity or consent finding.
    privacy_confidence = "high" if direct else "medium" if indirect >= 2 else "low"
    clean = canonical(text)
    quality = set()
    if len(clean) < 24 or len(clean.split()) < 5:
        quality.add("insufficient_context")
    if len(set(clean.split())) <= 3:
        quality.add("low_lexical_variety")
    if CORRUPT.search(text):
        quality.add("possible_corruption")
    speaker = bool(SPEAKER.search(text))
    staff = bool(STAFF.search(text))
    authorship = "staff_note" if staff and not speaker else "citizen_candidate" if speaker and not staff and not quality else "uncertain"
    if staff:
        quality.add("staff_vocabulary")
    if not speaker:
        quality.add("no_citizen_voice_cue")
    road = bool(ROAD_TERMS.search(text))
    garbage = bool(GARBAGE_TERMS.search(text))
    category = None
    category_evidence = []
    if road != garbage:
        category = ROAD if road else GARBAGE
        category_evidence.append("road_keyword" if road else "garbage_keyword")
    elif road and garbage:
        category_evidence.append("mixed_pilot_keywords")
    else:
        category_evidence.append("no_pilot_keyword")
    if source_category is None:
        category_evidence.append("missing_source_category")
    elif category and source_category != category:
        category_evidence.append("keyword_source_mismatch")
    scripts = [name for name, pattern in (("devanagari", DEVANAGARI), ("kannada", KANNADA), ("latin", LATIN)) if pattern.search(text)]
    language = "unknown"
    if len(scripts) > 1:
        language = "mixed_script"
    elif scripts == ["devanagari"]:
        language = "devanagari_script"
    elif scripts == ["kannada"]:
        language = "kannada_script"
    elif scripts == ["latin"]:
        language = "hinglish_hint" if HINGLISH_HINT.search(text) else "english_hint" if ENGLISH_HINT.search(text) else "latin_undetermined"
    return {
        "machine_screening_status": "screened",
        "machine_privacy_risk": risk,
        "privacy_confidence": privacy_confidence,
        "privacy_evidence_codes": sorted(privacy),
        "redaction_recommended": direct or indirect >= 2,
        "exclusion_recommended": "insufficient_context" in quality and "low_lexical_variety" in quality,
        "machine_authorship_suggestion": authorship,
        "authorship_evidence_codes": sorted(quality | ({"citizen_voice_cue"} if speaker else set())),
        "machine_category_suggestion": category,
        "category_evidence_codes": category_evidence,
        "machine_language_suggestion": {"value": language, "provenance": "machine_predicted", "evidence_codes": scripts},
        "quality_flags": sorted(quality),
    }


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _frozen_inputs() -> tuple[list[dict], dict, dict]:
    paths = {"processed": PROCESSED, "split": SPLIT, "queue": QUEUE, "manifest": MANIFEST}
    if any(file_digest(path) != EXPECTED[name] for name, path in paths.items()):
        raise ValueError("Frozen Phase 4 input checksum changed; stop before screening")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["processed_sha256"] != EXPECTED["processed"] or manifest["row_count"] != 1000:
        raise ValueError("Source manifest does not match frozen processed collection")
    rows = _read_jsonl(PROCESSED)
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    ids = [row["record_id"] for row in rows]
    assignment = {record_id: name for name, members in split["splits"].items() for record_id in members}
    if len(ids) != 1000 or len(set(ids)) != 1000 or set(ids) != set(assignment):
        raise ValueError("Frozen split does not cover exactly 1,000 unique source IDs")
    if len(queue["items"]) != 30 or not {item["record_id"] for item in queue["items"]} <= set(ids):
        raise ValueError("Phase 4 review queue changed")
    if any(row.get("privacy_status") != "pending_human_review" or row.get("data_kind") != "real" for row in rows):
        raise ValueError("Source contains non-pending or non-real rows")
    return rows, assignment, queue


def screen_all() -> tuple[list[dict], dict]:
    rows, assignment, queue = _frozen_inputs()
    minimal_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if file_digest(MINIMAL) != minimal_manifest["minimal_sha256"]:
        raise ValueError("Minimized title source checksum changed")
    minimal_rows = _read_jsonl(MINIMAL)
    minimal_by_id = {row["record_id"]: row for row in minimal_rows}
    if len(minimal_by_id) != 1000 or set(minimal_by_id) != {row["record_id"] for row in rows}:
        raise ValueError("Minimized title source IDs differ")
    queue_ids = {item["record_id"] for item in queue["items"]}
    assessed = []
    for row in rows:
        result = assess(row["complaint_text"], row.get("privacy_flags", []), row.get("category"))
        title = minimal_by_id[row["record_id"]]["title"]
        if (bool(ROAD_TERMS.search(title)) != bool(GARBAGE_TERMS.search(title))
                and bool(ROAD_TERMS.search(row["complaint_text"])) != bool(GARBAGE_TERMS.search(row["complaint_text"]))
                and bool(ROAD_TERMS.search(title)) != bool(ROAD_TERMS.search(row["complaint_text"]))):
            result["quality_flags"].append("title_description_pilot_topic_conflict")
        result.update({"record_id": row["record_id"], "split": assignment[row["record_id"]],
                       "source_category": row.get("category"), "source_subcategory_present": bool(row.get("source_subcategory")),
                       "phase4_queue": row["record_id"] in queue_ids, "ruleset_version": RULESET,
                       "source_processed_sha256": EXPECTED["processed"], "training_eligibility": False})
        assessed.append(result)
    # Deterministic metadata-only candidate pairs. No external embeddings/models.
    exact = defaultdict(list)
    templates = defaultdict(list)
    for row in rows:
        value = canonical(row["complaint_text"])
        exact[value].append(row["record_id"])
        normalized = re.sub(r"\b\d+\b", "#", value)
        templates[normalized].append(row["record_id"])
    related = defaultdict(set)
    reason_by_id = defaultdict(set)
    for groups in (exact, templates):
        for members in groups.values():
            if len(members) > 1:
                for member in members:
                    related[member].update(set(members) - {member})
                    reason_by_id[member].add("exact_or_number_template")
    # High-overlap token-set heuristic. Candidates stay candidates and cannot
    # change frozen split membership or become verified duplicate labels.
    token_sets = [(row["record_id"], set(canonical(row["complaint_text"]).split())) for row in rows]
    for index, (left_id, left) in enumerate(token_sets):
        if len(left) < 10:
            continue
        for right_id, right in token_sets[:index]:
            if len(right) < 10 or abs(len(left) - len(right)) > 6:
                continue
            shared = len(left & right)
            if shared >= 8 and shared / len(left | right) >= .82:
                related[left_id].add(right_id)
                related[right_id].add(left_id)
                reason_by_id[left_id].add("high_token_overlap")
                reason_by_id[right_id].add("high_token_overlap")
    # Weak cross-language candidate heuristic: same fairly specific title,
    # publisher category and creation day, but different script/lexical hint.
    # It cannot establish a translation or catch paraphrases with new titles.
    by_id = {item["record_id"]: item for item in assessed}
    title_groups = defaultdict(list)
    for row in rows:
        raw = minimal_by_id[row["record_id"]]
        title_tokens = canonical(raw["title"]).split()
        if len(title_tokens) >= 5:
            title_groups[(tuple(title_tokens), raw.get("created_at", "")[:10], row.get("category"))].append(row["record_id"])
    for members in title_groups.values():
        for index, left_id in enumerate(members):
            for right_id in members[:index]:
                left_lang = by_id[left_id]["machine_language_suggestion"]["value"]
                right_lang = by_id[right_id]["machine_language_suggestion"]["value"]
                if left_lang != right_lang:
                    related[left_id].add(right_id)
                    related[right_id].add(left_id)
                    reason_by_id[left_id].add("same_title_date_cross_language_hint")
                    reason_by_id[right_id].add("same_title_date_cross_language_hint")
    cross_split = 0
    for record_id, peers in related.items():
        by_id[record_id]["duplicate_candidate_ids"] = sorted(peers)
        by_id[record_id]["duplicate_evidence_codes"] = sorted(reason_by_id[record_id])
        if any(assignment[record_id] != assignment[peer] for peer in peers):
            cross_split += 1
    for item in assessed:
        item.setdefault("duplicate_candidate_ids", [])
        item.setdefault("duplicate_evidence_codes", [])
        if item["phase4_queue"]:
            batch = "audit_30"
        elif item["machine_privacy_risk"] == "high" or item["exclusion_recommended"]:
            batch = "high_privacy_or_exclusion"
        elif item["machine_privacy_risk"] == "uncertain" or item["machine_authorship_suggestion"] == "uncertain" or "keyword_source_mismatch" in item["category_evidence_codes"] or item["duplicate_candidate_ids"]:
            batch = "ambiguous_quality_or_label"
        elif item["source_category"] in {ROAD, GARBAGE}:
            batch = "pilot_candidate"
        else:
            batch = "representative_low_risk"
        item["review_batch"] = batch
    counts = {"screened": len(assessed), "privacy_risk": dict(Counter(item["machine_privacy_risk"] for item in assessed)),
              "exclusion_recommended": sum(item["exclusion_recommended"] for item in assessed),
              "batch": dict(Counter(item["review_batch"] for item in assessed)),
              "authorship_suggestion": dict(Counter(item["machine_authorship_suggestion"] for item in assessed)),
              "language_suggestion": dict(Counter(item["machine_language_suggestion"]["value"] for item in assessed)),
              "category_suggestion": dict(Counter(item["machine_category_suggestion"] or "none" for item in assessed)),
              "privacy_evidence": dict(Counter(code for item in assessed for code in item["privacy_evidence_codes"])),
              "quality_evidence": dict(Counter(code for item in assessed for code in item["authorship_evidence_codes"])),
              "quality_flags": dict(Counter(code for item in assessed for code in item["quality_flags"])),
              "category_evidence": dict(Counter(code for item in assessed for code in item["category_evidence_codes"])),
              "duplicate_candidate_rows": sum(bool(item["duplicate_candidate_ids"]) for item in assessed),
              "cross_split_duplicate_candidate_rows": cross_split,
              "source_category": dict(Counter(item["source_category"] or "unlabeled" for item in assessed)),
              "pilot_by_split": {category: dict(Counter(item["split"] for item in assessed if item["source_category"] == category)) for category in (ROAD, GARBAGE)},
              "human_reviewed": 0, "human_approved": 0, "human_excluded": 0, "training_eligible": 0}
    return sorted(assessed, key=lambda item: item["record_id"]), counts


def write_results(output: Path = OUTPUT) -> dict:
    output = Path(output)
    if not output.resolve().is_relative_to(DATA.resolve()) or output.suffix != ".jsonl":
        raise ValueError("Screening output must be JSONL under ignored ml/data")
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        if not output.exists() or not manifest_path.exists():
            raise ValueError("Incomplete existing screening result; stop and investigate")
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_inputs = {**EXPECTED, "minimal": json.loads(MANIFEST.read_text(encoding="utf-8"))["minimal_sha256"]}
        actual_inputs = {name: file_digest(path) for name, path in
                         (("processed", PROCESSED), ("split", SPLIT), ("queue", QUEUE), ("manifest", MANIFEST), ("minimal", MINIMAL))}
        if actual_inputs != expected_inputs:
            raise ValueError("Frozen screening inputs changed")
        if meta.get("ruleset_version") != RULESET or meta.get("input_sha256") != expected_inputs or meta.get("output_sha256") != file_digest(output):
            raise ValueError("Cached screening integrity mismatch")
        return meta["aggregate_counts"]
    rows, counts = screen_all()
    output.parent.mkdir(parents=True, exist_ok=True)
    _secure_path(output.parent, directory=True)
    descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        _secure_path(output)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = -1
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        inputs = {**EXPECTED, "minimal": json.loads(MANIFEST.read_text(encoding="utf-8"))["minimal_sha256"]}
        meta = {"schema": "nagrikos.phase5.machine_screening.v3", "ruleset_version": RULESET,
                "input_sha256": inputs, "output_sha256": file_digest(output), "aggregate_counts": counts,
                "interpretation": "Machine triage only; no privacy clearance, human decision or training approval."}
        descriptor = os.open(manifest_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        _secure_path(manifest_path)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(meta, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor != -1:
            os.close(descriptor)
        output.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    return counts


def write_review_plan(screening: Path = OUTPUT, output: Path = PLAN) -> dict:
    screening, output = Path(screening), Path(output)
    if not output.resolve().is_relative_to(DATA.resolve()) or output.suffix != ".json":
        raise ValueError("Review plan must be JSON under ignored ml/data")
    meta = json.loads(screening.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if meta["output_sha256"] != file_digest(screening) or meta["input_sha256"]["processed"] != EXPECTED["processed"]:
        raise ValueError("Screening checksum mismatch before planning")
    records = _read_jsonl(screening)
    if len(records) != 1000 or len({row["record_id"] for row in records}) != 1000:
        raise ValueError("Review plan requires 1,000 screened unique IDs")
    order = {"audit_30": 0, "high_privacy_or_exclusion": 1, "ambiguous_quality_or_label": 2,
             "pilot_candidate": 3, "representative_low_risk": 4}
    items = [{"record_id": row["record_id"], "split": row["split"], "source_category": row["source_category"],
              "review_batch": row["review_batch"], "machine_privacy_risk": row["machine_privacy_risk"]}
             for row in sorted(records, key=lambda row: (order[row["review_batch"]], row["record_id"]))]
    payload = {"schema": "nagrikos.phase5.review_plan.v1", "screening_sha256": meta["output_sha256"],
               "processed_sha256": EXPECTED["processed"], "split_sha256": EXPECTED["split"],
               "review_status": "pending_human_review", "counts": meta["aggregate_counts"]["batch"], "items": items}
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("Existing review plan differs; refusing overwrite")
        return payload["counts"]
    descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        _secure_path(output)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor != -1:
            os.close(descriptor)
        output.unlink(missing_ok=True)
        raise
    return payload["counts"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    counts = write_results(args.output)
    if args.output.resolve() == OUTPUT.resolve():
        write_review_plan(args.output)
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
