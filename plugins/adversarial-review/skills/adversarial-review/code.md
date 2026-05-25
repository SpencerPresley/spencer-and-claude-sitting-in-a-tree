# Code review — pin the exact slice

The reviewer judges only the slice you specify here. Be explicit; never default to a base-branch diff — a branch may carry several unrelated workstreams, and reviewing all of it is exactly the noise to avoid.

## Choose the slice from what the user said

Map the request to exactly one scope and its diff command:

| User means | Scope | Diff command |
|---|---|---|
| "my current/uncommitted changes" (default if they just say "my changes") | working tree | `git diff HEAD` plus untracked: `git status --short --untracked-files=all` |
| "what I've staged" | staged | `git diff --cached` |
| "this commit" / a SHA | one commit | `git show <sha>` (or `git diff <sha>^..<sha>`) |
| "these commits" / a range | range | `git diff <A>..<B>` |
| "just these files" / a feature slice | specific paths | `git diff HEAD -- <paths>` (or append `-- <paths>` to any command above) |

Rules:
- If the user did not say, default to the **narrowest** sensible scope — the uncommitted working tree — never a branch diff.
- If they named files or a feature, narrow to those paths even within a larger diff. Reviewing only the slice is the point.
- If the scope is ambiguous (e.g., "review my work" on a branch with several things in flight), ask which slice before dispatching.
- Do not run the diff here — you are only choosing *which* command. The reviewer runs it itself in its own context, so the diff stays out of this conversation.

## Capture intent

State in one sentence what this change is supposed to do (from the conversation, the commit message, or by asking once). The reviewer uses it to judge whether the change actually does that.

## Hand off

Return to `SKILL.md` step 3 and dispatch with `mode: code`, the chosen scope, the exact diff command, and the intent.
