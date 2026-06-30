---
name: layer-discipline
description: The rules for building Conseal's detection pipeline — cheap-to-expensive ordering, one layer at a time, gate before proceeding, and what every layer must emit. Use when starting or working on any detection layer.
---

# Layer Discipline

The pipeline is ordered cheap-and-certain first, expensive-and-contextual last. Each layer only has to reason about what earlier layers left ambiguous. This property is the whole point — protect it.

## The order
1. **Regex** — structured PII (phone, email, ID-shaped). Near-100% precision. Removes easy cases from the pool and records `normalized_value` for later duplicate linking.
2. **Dictionary / gazetteer** — closed-world entities (known IDs, known names) AND an allowlist of PII-shaped-but-safe strings that later layers must suppress.
3. **NER** — one benchmarked statistical model (GLiNER vs Presidio; ship one, keep the table). Respects the allowlist.
4. **LLM arbitration** — used sparingly, not as a primary detector. Catches relational/implicit PII where earlier layers found nothing but a trigger word exists, and resolves dictionary-vs-NER disagreements. Sliding window with overlap larger than the longest entity. Model flag-switched (cloud | gemma-local), same code path.
5. **Merge / differentiate** — one pure function applying the precedence table and risk tiers (see `pii-contract`).

## Non-negotiable rules
- Build exactly ONE layer per milestone. Do not stub or scaffold later layers.
- Do NOT start a layer until the previous layer's test gate is green.
- Each layer is its own service module, independently unit-tested against `fixtures/`.
- Every layer emits a per-candidate `reason` and a calibrated `confidence`.
- Every span asserts `text == original_text[start:end]`.
- Later layers must suppress anything inside a dictionary allowlist range.
- The LLM runs only where it adds value (empty-but-risky passages, disagreements) — never blindly over the whole document.

## Why cheap-first
It minimizes LLM calls (cost, latency, hallucination surface) by only invoking the model on the genuinely ambiguous remainder. State this ordering as a deliberate tradeoff in the writeup.
