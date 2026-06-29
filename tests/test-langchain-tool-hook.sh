#!/usr/bin/env bash
#
# Deterministic test for the fix-docstrings LangChain hook
# (plugins/fix-docstrings/hooks/scripts/langchain_tool_context.py).
#
# Feeds crafted hook payloads to the script and asserts the injected context,
# with no live model. Covers:
#   - UserPromptExpansion upfront scan of a directory target (lists @tool files)
#   - UserPromptExpansion upfront scan of a single-file target
#   - pre-seeding: the Read detector stays silent for files already listed
#   - graduated Read detection: FULL first, LIGHT after, dedup on re-read
#   - fallbacks: no target path, and model (Skill-tool) invocation
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$REPO_ROOT/plugins/fix-docstrings"
SCRIPT="$ROOT/hooks/scripts/langchain_tool_context.py"

FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"; find "${TMPDIR:-/tmp}" /tmp -maxdepth 1 -name "fix-docstrings-hooktest-*" -delete 2>/dev/null || true' EXIT

mkdir -p "$FIX/proj/sub"
TOOL_SRC=$'from langchain_core.tools import tool\n\n@tool\ndef act(x: str) -> str:\n    """Act."""\n    return x\n'
printf '%s' "$TOOL_SRC" > "$FIX/proj/a_tool.py"
printf '%s' "$TOOL_SRC" > "$FIX/proj/sub/c_tool.py"
printf '%s' "$TOOL_SRC" > "$FIX/outside_tool.py"
printf 'def plain():\n    return 1\n' > "$FIX/proj/plain.py"

PASS=0; FAIL=0
check() { # label expected actual
  if [ "$2" = "$3" ]; then printf '  ok   %s -> %s\n' "$1" "$3"; PASS=$((PASS+1))
  else printf '  FAIL %s: expected=%s actual=%s\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); fi
}
assert_lists() { # label needle haystack  (haystack must contain needle)
  if printf '%s' "$3" | grep -qF "$2"; then printf '  ok   %s lists %s\n' "$1" "$2"; PASS=$((PASS+1))
  else printf '  FAIL %s: missing %s\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}
refute_lists() { # label needle haystack  (haystack must NOT contain needle)
  if printf '%s' "$3" | grep -qF "$2"; then printf '  FAIL %s: should not list %s\n' "$1" "$2"; FAIL=$((FAIL+1))
  else printf '  ok   %s omits %s\n' "$1" "$2"; PASS=$((PASS+1)); fi
}

mk_expansion() { python3 -c 'import json,sys;print(json.dumps({"session_id":sys.argv[1],"hook_event_name":"UserPromptExpansion","command_name":"fix-docstrings","command_args":sys.argv[2],"cwd":sys.argv[3]}))' "$1" "$2" "$3"; }
mk_skill()     { python3 -c 'import json,sys;print(json.dumps({"session_id":sys.argv[1],"hook_event_name":"PostToolUse","tool_name":"Skill","tool_input":{"skill":"fix-docstrings"}}))' "$1"; }
mk_read()      { python3 -c 'import json,sys;print(json.dumps({"session_id":sys.argv[1],"hook_event_name":"PostToolUse","tool_name":"Read","tool_input":{"file_path":sys.argv[2]}}))' "$1" "$2"; }

trig()   { printf '%s' "$1" | python3 "$SCRIPT" trigger "$ROOT"; }
detect() { printf '%s' "$(mk_read "$1" "$2")" | python3 "$SCRIPT" detect "$ROOT"; }

# Program passed via -c so the piped hook output stays on stdin (a heredoc here
# would replace stdin with the script text).
classify() {
  python3 -c '
import json,sys
raw=sys.stdin.read().strip()
if not raw: print("SILENT"); sys.exit()
try:
    h=json.loads(raw)["hookSpecificOutput"]; ctx=h["additionalContext"]; ev=h["hookEventName"]
except Exception: print("MALFORMED"); sys.exit()
if ev=="UserPromptExpansion" and "these files:" in ctx: print("UPFRONT")
elif ev=="PostToolUse" and "in this file, read the LangChain" in ctx: print("FULL")
elif ev=="PostToolUse" and "also defines LangChain" in ctx: print("LIGHT")
else: print("OTHER")
'
}

echo "== Scenario A: directory target, upfront scan =="
S="hooktest-A-$$"
OUT="$(trig "$(mk_expansion "$S" "please fix @$FIX/proj/ now" "$FIX")")"
check     "A dir-trigger classification" UPFRONT "$(printf '%s' "$OUT" | classify)"
assert_lists "A" "$FIX/proj/a_tool.py" "$OUT"
assert_lists "A" "$FIX/proj/sub/c_tool.py" "$OUT"
refute_lists "A" "$FIX/proj/plain.py" "$OUT"
check     "A read of listed file is silent" SILENT "$(detect "$S" "$FIX/proj/a_tool.py" | classify)"
check     "A read of outside @tool file is LIGHT" LIGHT "$(detect "$S" "$FIX/outside_tool.py" | classify)"
check     "A read of plain file is silent" SILENT "$(detect "$S" "$FIX/proj/plain.py" | classify)"

echo "== Scenario B: single-file target, upfront scan =="
S="hooktest-B-$$"
OUT="$(trig "$(mk_expansion "$S" "@$FIX/proj/a_tool.py" "$FIX")")"
check     "B file-trigger classification" UPFRONT "$(printf '%s' "$OUT" | classify)"
assert_lists "B" "$FIX/proj/a_tool.py" "$OUT"
refute_lists "B" "$FIX/proj/sub/c_tool.py" "$OUT"
check     "B read of listed file is silent" SILENT "$(detect "$S" "$FIX/proj/a_tool.py" | classify)"

echo "== Scenario C: no target path -> Read-detector fallback =="
S="hooktest-C-$$"
check     "C trigger with no path is silent" SILENT "$(trig "$(mk_expansion "$S" "just fix the docstrings" "$FIX")" | classify)"
check     "C first @tool read is FULL" FULL "$(detect "$S" "$FIX/proj/a_tool.py" | classify)"
check     "C second @tool read is LIGHT" LIGHT "$(detect "$S" "$FIX/proj/sub/c_tool.py" | classify)"
check     "C re-read of first file is silent" SILENT "$(detect "$S" "$FIX/proj/a_tool.py" | classify)"

echo "== Scenario D: model (Skill-tool) invocation -> fallback =="
S="hooktest-D-$$"
check     "D skill trigger is silent (no target)" SILENT "$(trig "$(mk_skill "$S")" | classify)"
check     "D first @tool read is FULL" FULL "$(detect "$S" "$FIX/proj/a_tool.py" | classify)"

echo
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
