# adversarial-review

An adversarial reviewer subagent for **code** and **plans**. Instead of validating your work, it tries to break confidence in it — surfacing the strongest, best-supported reasons it should not ship — and it reviews **only the exact slice you name**.

## How it works

- A single skill (`adversarial-review`, named to match the plugin) is the entry point. It determines the mode (code or plan), pins the **exact slice** to review (modeled on the precision of the superpowers code-review request — name the exact diff/commits/files, not a vague "the branch"), captures intent, and dispatches.
- A read-only subagent (`adversarial-reviewer`) holds the adversarial persona as its **system prompt** (so the stance is reliable, not diluted by a "be helpful" base) and is locked to read-only tools (so "review only" is enforced, not merely requested). It does its own diff/file reading in its own context, judges only the slice, and returns a ship / do-not-ship verdict with prioritized findings.

## Usage

Invoke it in conversation — e.g. *"run the adversarial reviewer on the plan"* or *"adversarially review my staged changes, focus on the auth path"* — or directly:

```text
/adversarial-review [code|plan] [target] [focus...]
```

Scope is always explicit: working tree, staged, a named commit, an `A..B` range, or specific files for code; a plan file or section for plan. It never silently reviews the whole branch.

## Design

The reviewer's system prompt fuses a disciplined finding bar (what counts as a real, author-would-fix bug) with an adversarial stance (default skepticism, an attack-surface taxonomy, "try to disprove it"). It is review-only and never edits. The slice-specification approach embodies the precision of the superpowers code-review pattern without depending on that plugin.
