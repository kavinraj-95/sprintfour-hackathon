"""Ad-hoc inspector for the dictionary detection layer.

Run from the backend/ directory so imports resolve:

    .venv/bin/python inspect_dictionary.py
        -> runs over the sample fixture with a demo known-list + default allowlist

    .venv/bin/python inspect_dictionary.py --known "Jane Doe:PERSON,AB-12:ID_NUMBER" \
                                           --allow "Acme Corp,High Court" \
                                           --text "Jane Doe at Acme Corp, ref AB-12."
        -> runs over your own text/lists. --known items are TEXT:TYPE pairs.
"""
import argparse

import config
from models.contract import PiiType
from services.detection import dictionary_layer
from services.detection.dictionary_layer import KnownEntity

parser = argparse.ArgumentParser()
parser.add_argument("--text", help="text to scan (defaults to the sample fixture)")
parser.add_argument("--known", help="comma-separated TEXT:TYPE pairs")
parser.add_argument("--allow", help="comma-separated allowlist terms (overrides default)")
args = parser.parse_args()

text = args.text or (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")

if args.known is not None:
    known = []
    for pair in filter(None, args.known.split(",")):
        value, _, type_name = pair.rpartition(":")
        known.append(KnownEntity(value.strip(), PiiType(type_name.strip())))
else:
    # Demo closed-world list for the fixture (the parties known for this matter).
    known = [
        KnownEntity("Margaret Holloway", PiiType.PERSON),
        KnownEntity("Daniel Okafor", PiiType.PERSON),
        KnownEntity("CR-88341-AC", PiiType.ID_NUMBER),
    ]

kwargs = {"known_entities": known}
if args.allow is not None:
    kwargs["allowlist_terms"] = [t.strip() for t in args.allow.split(",") if t.strip()]

result = dictionary_layer.detect(text, **kwargs)

print(f"\nKNOWN-ENTITY SPANS ({len(result.spans)}):")
for s in result.spans:
    print(f"  [{s.start:>3}:{s.end:<3}] {s.type.value:<10} {s.text!r}")
    print(f"        conf={s.confidence}  source={s.source}  reason={s.reason}")
    assert s.text == text[s.start : s.end]

print(f"\nALLOWLIST RANGES ({len(result.allowlist)}) — later layers must suppress these:")
for r in result.allowlist:
    print(f"  [{r.start:>3}:{r.end:<3}] {r.text!r}  ({r.reason})")
    assert r.text == text[r.start : r.end]

print("\noffset rule holds for every span and allowlist range.")
