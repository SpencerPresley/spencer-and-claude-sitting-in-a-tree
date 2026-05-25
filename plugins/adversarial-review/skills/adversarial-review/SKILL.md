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

This is the important part: the reviewer must judge only the slice the user wants — never the whole branch or unrelated work. The procedure differs by mode; read the matching reference and follow it:

- **code mode:** read `${CLAUDE_SKILL_DIR}/code.md` and follow it to pin the exact diff slice and command.
- **plan mode:** read `${CLAUDE_SKILL_DIR}/plan.md` and follow it to pin the exact plan/section.

### 3. Dispatch

Call the Agent tool with `subagent_type: adversarial-reviewer` and a `prompt` built from this template. Do not add persona instructions — the agent owns those.

```
mode: <code|plan>
Slice: <the explicit scope from step 2>
How to see it: <exact diff command(s) for code | plan path/section for plan>
Intent: <one sentence: what this change/plan is supposed to achieve>
Focus: <the focus arguments, or "none">
Review only this slice. Verify findings against the actual code/plan before reporting.
```

### 4. Return

Relay the reviewer's verdict and findings verbatim. Do not fix anything, soften findings, or start revising — unless the user asks.
