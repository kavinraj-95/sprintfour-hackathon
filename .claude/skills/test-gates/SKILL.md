---
name: test-gates
description: How Conseal's milestone test gates work and the rule that a failing gate blocks the next milestone. Use at the end of every milestone.
---

# Test Gates

Every milestone ends with a gate. A gate is a small set of concrete, checkable assertions. You may not begin the next milestone until the current gate is green.

## The rule
- If a gate fails, FIX IT before doing anything else. Never stack an unverified layer on an unverified layer.
- A gate is green only when every assertion in it passes — not "mostly", not "the important ones".
- If a gate cannot be met (e.g. raster redaction can't be proven clean in the time box), do not fake it: cut the feature, document the omission as a deliberate tradeoff, and adjust the demo to use the path that works.

## Gate format
Each gate lists:
- The exact assertions (what must be true), phrased so they can be checked by running a test or clicking through the UI.
- A precision check where relevant (the layer must NOT flag things it shouldn't — overreach fails the gate just as much as misses).
- The offset assertion for any new span-creating code.

## What a good gate run looks like
1. Run the layer's unit test (or click the named UI states).
2. Confirm every assertion, including the negative/precision ones.
3. Confirm no earlier gate regressed (run the prior tests too).
4. Only then proceed.

## Why this matters here
The product's entire premise is catching mistakes that slip through. A pipeline assembled from unverified layers is exactly the silent-failure mode the product is meant to prevent — so the build process must hold itself to the same standard it sells.
