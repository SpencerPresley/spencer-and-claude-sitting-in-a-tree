# Plan review — pin the exact plan/slice

The reviewer judges only the plan (or section) you specify. Be explicit.

## Identify the plan

- If the user gave a file path, that is the plan — pass the path so the reviewer reads it in its own context.
- If they referenced "the plan" from the conversation, resolve it to a concrete file path or the specific text.
- If they want only part of it (a phase, a section, a single decision), narrow to that section and say so explicitly — the reviewer should challenge that slice, not the whole document.
- If you cannot identify a concrete plan, ask before dispatching.

## Capture intent

State in one sentence what shipping this plan is meant to achieve. The reviewer uses it to judge whether the approach actually serves that goal.

## Hand off

Return to `SKILL.md` step 3 and dispatch with `mode: plan`, the plan path (and section, if narrowed), and the intent.
