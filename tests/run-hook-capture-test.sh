#!/usr/bin/env bash
#
# Capture the real stdin payloads Claude Code hands to our hook events, so we
# can see the undocumented bits — the command_name for a slash-command skill,
# and the tool_input.skill for the Skill tool — instead of guessing matchers.
#
# Two scenarios, both headless (`claude -p`, haiku, low effort):
#   manual  /internal-plugin-testing ...      -> UserPromptExpansion (+ Read)
#   model   "invoke the ... skill"            -> PostToolUse[Skill]   (+ Read)
#
# Hooks come from .claude/hooks.json (a hooks-only settings file that Claude
# Code does NOT auto-load), passed explicitly via --settings. Captures land in
# tests/outputs/ (gitignored).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export CLAUDE_PROJECT_DIR="$REPO_ROOT"   # fallback so the hook command resolves

OUT="$REPO_ROOT/tests/outputs"
rm -f "$OUT"/*.json 2>/dev/null || true
mkdir -p "$OUT"

COMMON=(--print --model haiku --effort low
        --settings "$REPO_ROOT/.claude/hooks.json"
        --dangerously-skip-permissions)

echo "=== Scenario 1: manual slash-command invocation (/internal-plugin-testing) ==="
CAPTURE_LABEL=manual claude "${COMMON[@]}" \
  "/internal-plugin-testing Run the test and report back as instructed." \
  || echo "[claude exited non-zero]"
echo

echo "=== Scenario 2: model-driven skill invocation (Skill tool) ==="
CAPTURE_LABEL=model claude "${COMMON[@]}" \
  "Invoke the internal-plugin-testing skill using your Skill tool, then follow its instructions exactly." \
  || echo "[claude exited non-zero]"
echo

echo "=== Captured payloads in tests/outputs/ ==="
shopt -s nullglob
files=("$OUT"/*.json)
if [ ${#files[@]} -eq 0 ]; then
  echo "NO CAPTURES — hooks did not fire. Check that --settings loaded and CLAUDE_PROJECT_DIR resolved."
  exit 1
fi
for f in "${files[@]}"; do
  echo "--- $(basename "$f") ---"
  python3 - "$f" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for k in ("hook_event_name", "command_name", "command_args", "command_source",
          "expansion_type", "tool_name"):
    if k in d:
        print(f"  {k}: {d[k]!r}")
if isinstance(d.get("tool_input"), dict):
    ti = d["tool_input"]
    for k in ("skill", "file_path"):
        if k in ti:
            print(f"  tool_input.{k}: {ti[k]!r}")
PY
done
echo
echo "Done. Full JSON is in tests/outputs/."
