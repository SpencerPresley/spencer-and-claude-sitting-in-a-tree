# adversarial-review

An adversarial reviewer for code or plans. It reviews only the exact slice you name and reports the strongest, best-supported reasons it should not ship. It does not validate, and it never edits.

## How it works

- The `adversarial-review` skill is the entry point. It stays visible to Claude so it can pair the exposed reviewer agent with the instructions that prepare a good request.
- The skill pins the mode, exact target, collection guidance, intent, and focus, then dispatches the reviewer with a compact request.
- The `adversarial-reviewer` subagent holds the adversarial stance as its system prompt. Its prompt follows a Codex-style review contract: attack surface, review method, finding bar, grounding rules, output contract, and final self-check. It returns human-readable Markdown, not JSON, unless you ask for JSON.

Review-only is enforced by the agent's instructions plus a minimal toolset (Read, Grep, Glob, and Bash, with Bash reserved for read-only inspection such as `git`). The reviewer inherits the session's model and effort, so review depth tracks the model you're running.

## Usage

In conversation:

> "adversarially review my staged changes"
> "red-team the plan at docs/plan.md, focus on the migration step"

Or directly:

```
/adversarial-review [code|plan] [target] [focus...]
```

Scope is always explicit — working tree, staged, a commit, an `A..B` range, or specific files (code); a plan file or section (plan). It never silently reviews the whole branch.
