"""Select privacy-safe case IDs for local human annotation review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def sample(split: dict, per_split: int = 5) -> dict:
    if per_split < 1:
        raise ValueError("per_split must be positive")
    return {"version": 1, "purpose": "local_manual_review_only", "case_ids_by_split": {name: sorted(split["splits"][name])[:per_split] for name in ("train", "validation", "test")}, "review_questions": ["Is this genuine citizen complaint text or a categorical descriptor?", "Is any direct or indirect personal information present after automated redaction?", "Is the source category reliable and independent of the text field?", "Would using this field as a model input leak the target label?", "Is the source jurisdiction applicable to the proposed task?"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-split", type=int, default=5)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite review sample: {args.output}")
    result = sample(json.loads(args.split.read_text(encoding="utf-8")), args.per_split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "case_count": sum(map(len, result["case_ids_by_split"].values()))}))


if __name__ == "__main__":
    main()
