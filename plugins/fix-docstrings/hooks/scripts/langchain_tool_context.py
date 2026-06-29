#!/usr/bin/env python3
"""Inject the LangChain `@tool` docstring rules just-in-time during fix-docstrings.

The fix-docstrings skill no longer mentions LangChain at all. Instead, this hook
notices when the skill is active and a Python file containing LangChain `@tool`
functions is read, then injects a pointer to the parser-safe docstring
reference — exactly when it is relevant, for the specific file in hand, and only
once per run. That keeps the skill body lean for the common (non-LangChain) case
while still protecting tool schemas when they're actually present.

Only the `@tool` decorator is detected: it is the path that parses the docstring
into the tool schema. `StructuredTool` does not parse the docstring on its own.

Modes (argv[1]):
  trigger  Mark the skill active for this session. Fired both by
           UserPromptExpansion (direct `/fix-docstrings ...`) and by PostToolUse
           on the Skill tool (when the model invokes the skill itself), so every
           invocation route arms the detector.
  detect   Fired by PostToolUse on Read. If the skill is active and the file just
           read defines LangChain `@tool` functions, emit the reference pointer
           as additionalContext and latch so we don't repeat it.

argv[2] is CLAUDE_PLUGIN_ROOT, used to resolve the reference file path.

State lives in two per-session marker files under the temp dir:
  fix-docstrings-<session>.active    set by `trigger`
  fix-docstrings-<session>.injected  set by `detect` after one injection
The `.active` gate is what keeps `detect` cheap and silent on the Read calls of
every other session — without it this hook would fire on every Python read.
"""
import json
import os
import re
import sys
import tempfile

REFERENCE_REL = "skills/fix-docstrings/references/langchain-tool-docstrings.md"

# `@tool` used as a decorator: bare `@tool` or `@tool(...)`, at line start.
TOOL_DECORATOR = re.compile(r"^\s*@tool\b", re.MULTILINE)
# Any LangChain import — paired with the decorator this is a strong tool signal.
LANGCHAIN_IMPORT = re.compile(r"^\s*(?:from\s+langchain|import\s+langchain)", re.MULTILINE)


def flag_path(kind, session_id):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
    return os.path.join(tempfile.gettempdir(), f"fix-docstrings-{safe}.{kind}")


def read_event():
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def mode_trigger(event):
    """Arm the detector for this session if the skill being invoked is ours."""
    session_id = event.get("session_id", "")
    if event.get("hook_event_name") == "UserPromptExpansion":
        name = event.get("command_name", "") or ""
    else:  # PostToolUse on the Skill tool
        name = (event.get("tool_input") or {}).get("skill", "") or ""
    if "fix-docstrings" not in name:
        return
    open(flag_path("active", session_id), "w").close()
    # Reset the once-per-run latch so a fresh invocation can inject again.
    injected = flag_path("injected", session_id)
    if os.path.exists(injected):
        os.remove(injected)


def mode_detect(event, plugin_root):
    """If a just-read file defines LangChain @tool functions, inject the rules."""
    session_id = event.get("session_id", "")
    if not os.path.exists(flag_path("active", session_id)):
        return
    injected = flag_path("injected", session_id)
    if os.path.exists(injected):
        return

    file_path = (event.get("tool_input") or {}).get("file_path", "") or ""
    if not file_path.endswith(".py"):
        return
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            source = handle.read()
    except OSError:
        return
    if not (TOOL_DECORATOR.search(source) and LANGCHAIN_IMPORT.search(source)):
        return

    reference = os.path.join(plugin_root, REFERENCE_REL)
    context = (
        f"`{file_path}` defines LangChain `@tool` functions. LangChain parses "
        f"these docstrings to build the tool's input schema, so the standard "
        f"Google-style `(type)` annotations and rich formatting (bullets, "
        f"tables, nested entries) can silently corrupt or drop arguments. "
        f"Before fixing any docstrings in this file, read the LangChain tool "
        f"docstring rules at `{reference}` and apply them to every `@tool` "
        f"function."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))
    open(injected, "w").close()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    plugin_root = (
        sys.argv[2] if len(sys.argv) > 2 else os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    )
    event = read_event()
    if mode == "trigger":
        mode_trigger(event)
    elif mode == "detect":
        mode_detect(event, plugin_root)


if __name__ == "__main__":
    main()
