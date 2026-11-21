"""Create deterministic, complaint-grouped research splits; no model training."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


def canonical(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def related(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 40:
        return False
    if abs(len(left) - len(right)) > max(len(left), len(right)) * .12:
        return False
    return SequenceMatcher(None, left, right, autojunk=False).ratio() >= .90


def template_related(left: str, right: str) -> bool:
    """Conservatively group long repeated sentence frames with changed slots."""
    if min(len(left), len(right)) < 45:
        return False
    left_words = re.sub(r"\b\d+\b", "#", left).split()
    right_words = re.sub(r"\b\d+\b", "#", right).split()
    if min(len(left_words), len(right_words)) < 7:
        return False
    left_grams = {tuple(left_words[i:i + 3]) for i in range(len(left_words) - 2)}
    right_grams = {tuple(right_words[i:i + 3]) for i in range(len(right_words) - 2)}
    union = left_grams | right_grams
    overlap = left_grams & right_grams
    if len(overlap) < 4 or len(overlap) / len(union) < .65:
        return False
    return SequenceMatcher(None, left, right, autojunk=False).ratio() >= .82


def group_records(records: list[dict], template_mode: bool = False) -> list[list[int]]:
    if len(records) > 5000:
        raise ValueError("Near-duplicate checks are bounded at 5,000 records per run")
    parent = list(range(len(records)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def unite(a: int, b: int) -> None:
        parent[root(a)] = root(b)

    texts = [canonical(row["complaint_text"]) for row in records]
    trigrams = [{text[index:index + 3] for index in range(max(0, len(text) - 2))} for text in texts]
    # Cheap character-shingle screening avoids expensive alignment for unrelated narratives.
    # The threshold is deliberately loose; exact matches bypass it entirely.
    for i in range(len(records)):
        for j in range(i):
            if texts[i] == texts[j]:
                unite(i, j)
                continue
            if min(len(texts[i]), len(texts[j])) < 40:
                continue
            shared = len(trigrams[i] & trigrams[j])
            union = len(trigrams[i] | trigrams[j])
            if not union or shared / union < .50:
                continue
            if related(texts[i], texts[j]) or (template_mode and template_related(texts[i], texts[j])):
                unite(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(len(records)):
        groups.setdefault(root(i), []).append(i)
    return list(groups.values())


def assign(records: list[dict], template_mode: bool = False) -> dict:
    ids = [row["record_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record IDs")
    groups = group_records(records, template_mode)
    allocations = {"train": [], "validation": [], "test": []}
    grouping = []
    for group in groups:
        members = sorted(ids[i] for i in group)
        key = members[0]
        bucket = int(hashlib.sha256(key.encode("ascii")).hexdigest()[:8], 16) / 0xFFFFFFFF
        split = "train" if bucket < .70 else "validation" if bucket < .85 else "test"
        allocations[split].extend(members)
        grouping.append({"group_id": hashlib.sha256("|".join(members).encode()).hexdigest(), "split": split, "size": len(members)})
    return {"version": 1, "method": "stable_group_hash_70_15_15" + ("_template_aware" if template_mode else ""), "near_duplicate_threshold": .90, "template_aware": template_mode, "source_ids": sorted({row["source_id"] for row in records}), "splits": {key: sorted(value) for key, value in allocations.items()}, "groups": sorted(grouping, key=lambda group: group["group_id"]), "counts": {key: len(value) for key, value in allocations.items()}, "limitations": ["Date-based temporal evaluation is not performed; avoid closure/ETA claims until dated source data is reviewed.", "All records require a manual privacy review before sharing or model training.", "Cross-language paraphrases and rewritten templates may evade automated grouping; review before training."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template-aware", action="store_true", help="Group repeated sentence frames as well as near duplicates")
    args = parser.parse_args()
    with args.input.open(encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite split manifest: {args.output}")
    result = assign(records, args.template_aware)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": result["counts"]}))


if __name__ == "__main__":
    main()
