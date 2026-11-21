"""Aggregate-only scan for direct and indirect identifier patterns in local JSONL.

Never prints text, source IDs, or record IDs. This is a triage aid, not privacy clearance.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from ml.scripts.preprocess import ADDRESS, EMAIL, IDENTIFIER, PHONE, US_PHONE

PATTERNS = {
    "email": EMAIL,
    "phone_indian": PHONE,
    "phone_us": US_PHONE,
    "selected_identifier": IDENTIFIER,
    "street_address": ADDRESS,
    "url": re.compile(r"(?i)https?://|www\."),
    "handle": re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}"),
    "coordinate_pair": re.compile(r"(?<!\d)\d{1,2}\.\d{4,}\s*,\s*\d{1,3}\.\d{4,}(?!\d)"),
    "long_number": re.compile(r"(?<!\d)\d{8,}(?!\d)"),
    "six_digit_number": re.compile(r"(?<!\d)\d{6}(?!\d)"),
}


def scan(path: Path, text_fields: tuple[str, ...]) -> dict:
    rows = 0
    strings = 0
    per_row: Counter = Counter()
    per_string: Counter = Counter()
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL record at line {number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected object at line {number}")
            rows += 1
            seen = set()
            for field in text_fields:
                value = record.get(field)
                if value is None:
                    continue
                if not isinstance(value, str):
                    raise ValueError(f"Non-text value for {field} at line {number}")
                strings += 1
                for name, pattern in PATTERNS.items():
                    if pattern.search(value):
                        per_string[name] += 1
                        seen.add(name)
            per_row.update(seen)
    return {"rows": rows, "text_fields": list(text_fields), "strings_scanned": strings,
            "matching_rows": {name: per_row[name] for name in PATTERNS},
            "matching_strings": {name: per_string[name] for name in PATTERNS},
            "interpretation": "Pattern matches require local review; zero matches does not establish deidentification."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--fields", nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps(scan(args.input, tuple(args.fields)), sort_keys=True))


if __name__ == "__main__":
    main()
