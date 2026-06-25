# Codex Integration (OpenAI GPT-5.5) — extended

This build makes Codex's review commands **model-invokable** — you (Claude) can run Codex reviews directly, not just the user. Codex is a second AI: a read-only reviewer and a write-capable delegate.

_Codex routes to GPT-5.5 (OpenAI's latest); some plugin text still says GPT-5.4 — the same guidance applies._

## Critical rules (always apply)

- **Reviews are READ-ONLY. Never auto-apply fixes.** After presenting `codex:review` / `codex:adversarial-review` findings, STOP — don't edit a single file, even an obvious fix. Ask the user which to fix.
- **Return Codex output verbatim** — findings ordered by severity, exact file:line. No paraphrasing.
- **`codex:rescue` is write-capable** (Codex edits files); `review` / `adversarial-review` are read-only.

## Commands you can invoke

- `codex:review` — native read-only review of local git state.
- `codex:adversarial-review` — challenge-the-design review; takes focus text.
- `codex:rescue` — delegate write-capable work to the Codex agent.
- `codex:setup` — check CLI install / auth.

`/codex:status`, `/codex:result`, `/codex:cancel` are **user-only** — point the user there after backgrounding a job.

## Full guide

**Before running a Codex review or delegating work, invoke the `codex:using-codex` skill.** It has every flag, the review output schema, when-to-use guidance for each command, background-vs-wait, and how to prompt GPT-5.5. This briefing is just the menu + the safety rules; the skill is the manual.
