"""Ad-hoc inspector for the regex detection layer.

Usage (run from the backend/ directory so imports resolve):
    .venv/bin/python inspect_regex.py                  # runs over the sample fixture
    .venv/bin/python inspect_regex.py "your own text"  # runs over text you pass
    echo "piped text" | .venv/bin/python inspect_regex.py -
"""
import sys

import config
from services.detection import regex_layer

if len(sys.argv) > 1:
    text = sys.stdin.read() if sys.argv[1] == "-" else sys.argv[1]
else:
    text = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")

spans = regex_layer.detect(text)
print(f"{len(spans)} span(s) detected:\n")
for s in spans:
    norm = f"  norm={s.normalized_value!r}" if s.normalized_value else ""
    print(f"  [{s.start:>3}:{s.end:<3}] {s.type.value:<10} {s.text!r}")
    print(f"        conf={s.confidence}  source={s.source}  reason={s.reason}{norm}")
    # Proof of the offset rule, live:
    assert s.text == text[s.start : s.end]
print("\noffset rule holds for every span (text == original[start:end]).")
