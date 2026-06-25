# Codex skills available — guardrails

You have `codex:review` / `codex:adversarial-review` (read-only Codex reviews) and `codex:rescue` (write-capable delegation) in your invokable skill list.

Hard rules:
- **Reviews are READ-ONLY. Never auto-apply fixes** after review findings — not even obvious ones. Surface them and let the main thread or user decide.
- **Return Codex output verbatim** — don't paraphrase or summarize it.
- `codex:rescue` is **write-capable** (Codex may edit files). Only delegate substantial, clearly-bounded work; don't spawn nested Codex runs for trivial tasks.
- `codex:status` / `codex:result` / `codex:cancel` are user-only — you can't call them.

For the full guide (every flag, the review output schema, when to use each), invoke the `codex:using-codex` skill.
