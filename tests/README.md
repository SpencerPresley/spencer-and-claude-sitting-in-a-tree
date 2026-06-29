# tests

Throwaway instrumentation for discovering the exact stdin payloads Claude Code
hands to hook events — used to validate the `fix-docstrings` plugin's hook
design against reality instead of guessing undocumented fields.

## Run it

```bash
tests/run-hook-capture-test.sh
```

Two headless `claude -p` scenarios (haiku, low effort) exercise both ways a skill
gets activated. Hooks are loaded only for the run via
`--settings .claude/hooks.json` (Claude Code does **not** auto-load
`.claude/hooks.json` — only `settings.json` / `settings.local.json` — so this
config stays inert in normal sessions). Captured payloads land in
`tests/outputs/` (gitignored).

Pieces:
- `.claude/hooks.json` — hooks-only settings file; `tests/capture-hook-input.py`
  records each payload. The `UserPromptExpansion` matcher is empty on purpose so
  it fires on every slash command and reveals the real `command_name`.
- `.claude/skills/internal-plugin-testing/` — a minimal project skill that reads
  `scripts/hello.py` (to fire `PostToolUse[Read]`) and prints a canary.

## What it confirmed

| Activation | `UserPromptExpansion` | `PostToolUse[Skill]` | `PostToolUse[Read]` |
|---|---|---|---|
| `/skill` typed manually | ✅ fires | ❌ does **not** fire | ✅ fires |
| Model invokes the skill | ❌ does not fire | ✅ fires | ✅ fires |

- `UserPromptExpansion.command_name` is the **bare** skill name (`internal-plugin-testing`),
  not plugin-namespaced. `command_args` holds the rest of the prompt;
  `command_source` is `projectSettings` (would be `plugin` for an installed
  plugin — the docs example for a plugin command likewise shows a bare
  `command_name`).
- `PostToolUse[Skill].tool_input.skill` is the **bare** skill name.
- `PostToolUse[Read].tool_input.file_path` is an **absolute** path.

This is why `fix-docstrings` needs **both** a `UserPromptExpansion` hook (manual
`/fix-docstrings`) **and** a `PostToolUse[Skill]` hook (model invocation) to arm
its detector — neither path covers the other. The matcher `fix-docstrings` and
the script's substring check on the skill name both hold regardless of
namespacing.
