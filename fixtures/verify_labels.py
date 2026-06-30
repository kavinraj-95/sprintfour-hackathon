"""Independently verify every offset in labels.json against the document.

Run from anywhere:  python3 fixtures/verify_labels.py
Exits non-zero and prints each mismatch if the offset rule is violated.
This re-reads the written files (it does not trust the generator).
"""
import json
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parent
sample = (FIX / "sample-document.txt").read_text(encoding="utf-8")
labels = json.loads((FIX / "labels.json").read_text(encoding="utf-8"))

VALID_TYPES = {"PERSON", "ORG", "EMAIL", "PHONE", "ADDRESS", "ID_NUMBER", "OTHER"}

mismatches: list[str] = []
checked = 0


def check(entry: dict, group: str) -> None:
    global checked
    checked += 1
    start, end, text = entry["start"], entry["end"], entry["text"]
    if not (0 <= start <= end <= len(sample)):
        mismatches.append(f"[{group}] {entry['id']}: offsets [{start},{end}) out of range "
                          f"(doc len {len(sample)})")
        return
    actual = sample[start:end]
    if actual != text:
        mismatches.append(f"[{group}] {entry['id']}: text != sample[{start}:{end}]\n"
                          f"    labeled: {text!r}\n    sliced : {actual!r}")
    if entry["type"] not in VALID_TYPES:
        mismatches.append(f"[{group}] {entry['id']}: type {entry['type']!r} not in contract")


for s in labels["spans"]:
    check(s, "span")
for a in labels["allowlist"]:
    check(a, "allowlist")

# Cross-check the adversarial cases reference real span ids.
known_ids = {s["id"] for s in labels["spans"]} | {a["id"] for a in labels["allowlist"]}
for case in labels["adversarial_cases"]:
    for sid in case["span_ids"]:
        if sid not in known_ids:
            mismatches.append(f"[adversarial:{case['name']}] references unknown id {sid!r}")

# Confirm the duplicate-phone pair actually shares a normalized_value.
phones = {s["id"]: s for s in labels["spans"] if s["type"] == "PHONE"}
norms = {s.get("normalized_value") for s in phones.values()}
if len(phones) >= 2 and len(norms) != 1:
    mismatches.append(f"duplicate-phone link broken: normalized_values differ -> {norms}")

print(f"checked {checked} labeled offsets across "
      f"{len(labels['spans'])} spans + {len(labels['allowlist'])} allowlist")
if mismatches:
    print(f"\n{len(mismatches)} MISMATCH(ES):")
    for m in mismatches:
        print("  -", m)
    sys.exit(1)

print("OK: every label satisfies text == sample[start:end]; types valid; "
      "duplicate-phone link intact.")
