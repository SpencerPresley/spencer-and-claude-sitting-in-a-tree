---
name: adversarial-review
description: Run the adversarial reviewer on code or a plan. Use when the user asks to adversarially review, red-team, challenge, or pressure-test a specific change or plan — to find the strongest reasons it should not ship. Reviews only the exact slice the user names.
argument-hint: "[code|plan] [target] [focus...]"
---

## Adversarial review

You are setting up an adversarial review and dispatching it to the `adversarial-reviewer` subagent. You are the input builder, not the reviewer — do not review or fix anything yourself.

The reviewer wakes with no context, so your whole job is to hand it three things: the **mode**, the **exact slice** to review, and the **intent**. It then reviews only that slice.

### 1. Determine mode

- `code` — reviewing a code change/diff.
- `plan` — reviewing a plan/design/spec document.

Take it from the user's request ("review the plan" → plan; "review this diff/change" → code) or the first argument. If it is genuinely unclear, ask.

### 2. Pin the exact slice + intent

The reviewer must judge only the slice the user wants — never the whole branch or unrelated work. Pinning this precisely is the most important thing you do.

**Code mode — pin exactly the slice the user means, and give the command that produces it.** Common cases:

| User means | Diff command |
|---|---|
| "my changes" / uncommitted | `git diff HEAD` (+ untracked via `git status --short --untracked-files=all`) |
| "what I staged" | `git diff --cached` |
| "this commit" / a SHA | `git show <sha>` |
| "these commits" / a range | `git diff <A>..<B>` |
| "the whole branch" / "everything vs main" | `git diff <base>...HEAD` |
| "just these files" | append `-- <paths>` to any of the above |

The slice is whatever the user actually intends — a base-branch diff is completely fine when that's the scope they want. The thing to avoid is *silently* widening to the whole branch when they meant a piece of it: if the scope isn't explicit (e.g., "review my work" on a branch with several things in flight), ask or take the narrowest obvious read rather than guess broad. Don't run the diff yourself — you only pick the command; the reviewer runs it in its own context so the diff stays out of this conversation.

**Plan mode — pin the document (or section):**

- A file path → pass the path. "The plan" from the conversation → resolve it to a concrete path or the exact text.
- Only part of it (a phase, a section, one decision) → narrow to that and say so; the reviewer challenges that slice, not the whole document.
- If you can't identify a concrete plan, ask before dispatching.

**Intent (both modes):** state in one sentence what the change/plan is supposed to achieve. The reviewer uses it to judge whether the work serves that goal.

### 3. Dispatch

Call the Agent tool with `subagent_type: adversarial-review:adversarial-reviewer` (the agent is plugin-namespaced as `<plugin>:<agent>`; if your client lists it under a different prefix, use the available agent whose name ends in `:adversarial-reviewer`) and a `prompt` built from this template. Do not add persona instructions — the agent owns those.

```
mode: <code|plan>
Slice: <the explicit scope from step 2>
How to see it: <exact diff command(s) for code | plan path/section for plan>
Intent: <one sentence: what this change/plan is supposed to achieve>
Focus: <the focus arguments, or "none">
Review only this slice. Verify findings against the actual code/plan before reporting.
```

**Keep the reviewer sharp:** the `Intent` line says what the change/plan is *meant to achieve* — never why the chosen approach is *right*. Don't pre-justify the work. Pre-arguing it here, or softening its findings on the way back (step 4), are the two ways to blunt the reviewer — which defeats the entire point of running it.

### 4. Return

Relay the reviewer's verdict and findings verbatim. Do not fix anything, soften findings, or start revising — unless the user asks.
