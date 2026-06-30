# Conseal — Claude Code agents & skills

Drop the `.claude/` folder into the root of your Conseal project. Claude Code
auto-discovers agents and skills from there.

## Layout
```
.claude/
  agents/
    contract-keeper.md       # owns the shared contract; nobody else edits it
    pipeline-engineer.md     # builds detection layers one at a time, gated
    output-engineer.md       # redact + anonymize engines and the toggle
    ocr-engineer.md          # raster path, time-boxed, optional
    ux-engineer.md           # the correction experience (the judged deliverable)
    reviewer-demo.md         # runs last: fix list + demo + writeup
  skills/
    pii-contract/SKILL.md            # span shape, offset rule, merge precedence, risk tiers
    layer-discipline/SKILL.md        # cheap->expensive order, one layer at a time
    redaction-vs-anonymization/SKILL.md  # remove vs replace, the toggle, raster warning
    test-gates/SKILL.md              # gate format, failing gate blocks next milestone
```

## How they work together
- Invoke an **agent** with the matching milestone prompt from the handbook
  (e.g. "use the pipeline-engineer agent for Milestone 1 — regex").
- Agents read the relevant **skills** automatically; the milestone prompts also
  name them explicitly as a reminder.
- The **contract-keeper** is the only agent allowed to touch the contract files,
  which is what keeps the backend and frontend from drifting apart.

## Build order (sequential, gated)
setup → fixtures → regex → dictionary → NER → LLM → merge → output toggle →
OCR (optional) → UX → review/demo. Pass each Stop & Test gate before the next.
