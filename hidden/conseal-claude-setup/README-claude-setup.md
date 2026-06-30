# Claude Code setup for the Conseal hackathon

A ready-to-use team of subagents + skills for the Sprintfour "Conseal" solo hackathon,
tuned to the actual rubric (judgment, discovery, empathy, tradeoffs — not just working code).

## Install
Drop the contents into your project root so you have:

```
your-project/
  CLAUDE.md                      # project memory, auto-read by Claude Code
  .claude/
    agents/                      # 6 subagents
      product-strategist.md
      pii-detection-engineer.md
      backend-engineer.md
      frontend-engineer.md
      code-reviewer.md
      submission-writer.md
    skills/                      # 4 skills
      conseal-domain/SKILL.md
      pii-detection/SKILL.md
      redaction-ux-patterns/SKILL.md
      fullstack-scaffold/SKILL.md
```

Then start (or restart) Claude Code in that directory. **Subagents are loaded at session
start — restart the session after adding the files.** Run `/agents` to confirm all six are
listed, or just ask Claude to "use the product-strategist subagent".

## The team

| Agent | Role | Tools | Model |
|---|---|---|---|
| **product-strategist** | Discovery, edge cases, user empathy, tradeoffs — wins the rubric | read + research, no write | opus |
| **pii-detection-engineer** | The detection layer; mock/LLM swappable interface; span model | full | inherit |
| **backend-engineer** | API, document handling, the redaction engine | full | inherit |
| **frontend-engineer** | The review experience; how it *feels* | full | inherit |
| **code-reviewer** | Guards SE fundamentals; read-only | read + bash | sonnet |
| **submission-writer** | The writeup + demo script | read + write | inherit |

The four skills are attached to the agents that need them (via the `skills:` frontmatter)
**and** auto-load by description in the main session, so context stays consistent.

## How to drive it (suggested flow)
1. **Decide the problem first.** "Use the product-strategist to help me pick between the
   three problems and find the hard cases for the one I choose." This is where the rubric is won.
2. **Stand up the seam.** "Use the pii-detection-engineer to build the span contract and a
   MockDetector so the pipeline is deterministic." Your UX never waits on detection.
3. **Build backend then frontend.** Delegate to backend-engineer (routes/services/redaction
   engine), then frontend-engineer (the core flow for your chosen user).
4. **Review often.** After meaningful changes: "Use the code-reviewer on the recent diff."
5. **Find the one hard case** that proves discovery (e.g. the missed phone number, or an
   export that proves the original text is truly gone).
6. **Write the submission.** "Use the submission-writer to draft SUBMISSION.md and
   DEMO_SCRIPT.md from what we actually built and the cut-list."

## Notes / tuning
- **Models:** `product-strategist` is set to `opus` (reasoning-heavy) and `code-reviewer` to
  `sonnet` (fast/cheap); the rest `inherit` your session model. If your plan/allowlist
  doesn't include a model, change the `model:` line to `inherit`.
- **The `skills:` field** on agents preloads a skill into that agent's context. If your
  Claude Code version doesn't support it, it's harmless — the skill still auto-loads by
  description when relevant.
- Everything is **project-scoped** (`.claude/` in the repo). Move any file to `~/.claude/`
  to make it available across all your projects.
- Edit the agent bodies freely — they're just Markdown system prompts. Re-running `/agents`
  or restarting the session picks up changes.

## The one thing to remember
Working code is the floor. The competition is decided on judgment: which hard cases you
noticed and how thoughtfully you handled them — and the writeup's account of **what you
chose NOT to build, and why.** Build one deep, correct flow for one real user. Cut the rest,
and write the cuts down.
