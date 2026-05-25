# adversarial-review

An adversarial reviewer for code or plans. It reviews only the exact slice you name and reports the strongest, best-supported reasons it should not ship. It does not validate, and it never edits.

## How it works

- The `adversarial-review` skill is the entry point. It picks the mode (code or plan), pins the exact slice (specific diff / commits / files, or a plan file / section — never a vague "the branch"), captures the intent, and dispatches.
- The `adversarial-reviewer` subagent holds the adversarial stance as its system prompt. It reads the slice in its own context (running the diff itself), judges only that slice, and returns a verdict (ship / ship-with-fixes / do-not-ship) with prioritized findings. It only reviews — it never edits.

Review-only is enforced by the agent's instructions plus a minimal toolset (Read, Grep, Glob, and Bash — the latter only to run `git`). The reviewer inherits the session's model and effort, so review depth tracks the model you're running.

## Usage

In conversation:

> "adversarially review my staged changes"
> "red-team the plan at docs/plan.md, focus on the migration step"

Or directly:

```
/adversarial-review [code|plan] [target] [focus...]
```

Scope is always explicit — working tree, staged, a commit, an `A..B` range, or specific files (code); a plan file or section (plan). It never silently reviews the whole branch.
