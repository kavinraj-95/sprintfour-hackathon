# NER layer benchmark (Conseal pipeline, layer 3)

Scored over `fixtures/sample-document.txt` against the PERSON / ORG / ADDRESS entries in `labels.json`. A prediction is a true positive if it **overlaps** a ground-truth span of the same mapped type (NER boundaries are rarely exact, so overlap—not exact match—is the fair rule). The allowlisted org `Coastline Mutual` is **not** a positive: flagging it is a false positive.

## GLiNER: deliberately not run (a cut)

GLiNER (zero-shot, our labels at inference) was the other candidate. It requires `torch` (~0.5 GB) plus a transformer model download — too heavy for this prototype's footprint, so it was **cut**. Expected tradeoff: GLiNER would likely raise ADDRESS recall (it handles multi-token entities from a plain label well) at a large dependency and latency cost. We instead make Presidio cover ADDRESS with a targeted recognizer (below).

## Results

| Approach | P (person) | R (person) | P (address) | R (address) | F1 (overall) | latency/doc |
|---|---|---|---|---|---|---|
| Presidio (spaCy sm, out-of-box) | 0.75 | 1.00 | n/a | 0.00 | 0.75 | 35 ms |
| Presidio + street-address recognizer | 0.75 | 1.00 | 1.00 | 1.00 | 0.89 | 36 ms |

## Adversarial cases

- **name-with-no-anchor (`Daniel Okafor`)** — CAUGHT as PERSON. Presidio's statistical NER finds it with no title or format cue, which is exactly what regex/dictionary could not do.
- **full street address (`14 Brunswick Street, Fitzroy VIC 3065`)** — out-of-the-box Presidio MISSES it (spaCy `sm` produces no entity; it even tags `3065` as a date). The targeted street-address recognizer recovers it as ADDRESS. This is the deciding gap, and why ADDRESS coverage is an explicit augmentation.
- **allowlisted org (`Coastline Mutual`)** — Presidio FALSE-flags it as PERSON. The NER layer suppresses it using the dictionary layer's allowlist range, so it never reaches output. Without the allowlist this is a textbook NER false positive on a public name.

## Decision

Ship **Presidio + the street-address recognizer**. Rationale, in the order that matters here: (1) it gives full PERSON recall including the no-anchor name; (2) the added recognizer gives full ADDRESS recall, which plain Presidio lacks; (3) latency is a few ms/doc, far under any budget; (4) it avoids torch entirely. GLiNER is kept on the table (this file) should higher ADDRESS/PERSON recall on harder documents ever justify the dependency.
