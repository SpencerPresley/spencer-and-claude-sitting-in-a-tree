#!/usr/bin/env python3
"""Inject the LangChain `@tool` docstring rules just-in-time during fix-docstrings.

The fix-docstrings skill no longer mentions LangChain at all. Instead, this hook
notices when the skill is active and a Python file containing LangChain `@tool`
functions is read, then injects the parser-safe docstring rules — exactly when
they are relevant, for the specific file in hand. That keeps the skill body lean
for the common (non-LangChain) case while still protecting tool schemas when
they're actually present.

The injection is graduated, keyed to whether the reference is already in context
(a session-level fact), not to a single invocation:
  - The FIRST `@tool` file seen in the session gets the full pointer telling you
    to read the reference file.
  - Every LATER `@tool` file gets a light reminder to apply the rules you already
    read — no path, no "re-read" — since the reference is already in context.
Each file is flagged at most once; re-reads of the same file stay silent.

Only the `@tool` decorator is detected: it is the path that parses the docstring
into the tool schema. `StructuredTool` does not parse the docstring on its own.

Modes (argv[1]):
  trigger  Mark the skill active for this session. Fired both by
           UserPromptExpansion (direct `/fix-docstrings ...`) and by PostToolUse
           on the Skill tool (when the model invokes the skill itself), so every
           invocation route arms the detector. On the UserPromptExpansion path
           the typed target is available in command_args, so trigger also scans
           the named files/dirs up front and injects the exact list of `@tool`
           files (pre-seeding state so the Read detector won't repeat them).
  detect   Fired by PostToolUse on Read. If the skill is active and the file just
           read defines LangChain `@tool` functions, emit the full pointer (first
           time) or a light reminder (after) as additionalContext. This is the
           fallback for model invocation and for files outside the typed target.

argv[2] is CLAUDE_PLUGIN_ROOT, used to resolve the reference file path.

State lives in per-session marker files under the temp dir:
  fix-docstrings-<session>.active        set by `trigger`; gates `detect`
  fix-docstrings-<session>.referenced    set once the full pointer has been sent
  fix-docstrings-<session>.seen-<hash>   set per file already flagged
The `.active` gate is what keeps `detect` cheap and silent on the Read calls of
every other session — without it this hook would fire on every Python read.
"""
import hashlib
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


def seen_marker(session_id, file_path):
    digest = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:16]
    return flag_path(f"seen-{digest}", session_id)


def is_tool_file(path):
    """True if the .py file defines a LangChain `@tool` function."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            source = handle.read()
    except OSError:
        return False
    return bool(TOOL_DECORATOR.search(source) and LANGCHAIN_IMPORT.search(source))


# Guard so a pathological directory tree can't stall the hook past its timeout.
MAX_SCAN_FILES = 1000


def scan_targets(command_args, cwd):
    """Find `@tool` files among the file/dir paths named in command_args.

    Each whitespace token is resolved against cwd; a leading `@` (Claude's
    file-mention syntax) and trailing slashes/commas are stripped. Files are
    checked directly; directories are walked. Returns sorted absolute paths,
    bounded by MAX_SCAN_FILES.
    """
    found = set()
    budget = MAX_SCAN_FILES
    for token in (command_args or "").split():
        candidate = token.lstrip("@").rstrip("/,")
        if not candidate:
            continue
        path = candidate if os.path.isabs(candidate) else os.path.join(cwd or "", candidate)
        if os.path.isfile(path):
            if path.endswith(".py") and is_tool_file(path):
                found.add(os.path.abspath(path))
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for name in files:
                    if not name.endswith(".py"):
                        continue
                    budget -= 1
                    if budget < 0:
                        return sorted(found)
                    fpath = os.path.join(root, name)
                    if is_tool_file(fpath):
                        found.add(os.path.abspath(fpath))
    return sorted(found)


def read_event():
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def mode_trigger(event, plugin_root):
    """Arm the detector, and for a typed `/fix-docstrings <target>`, inject an
    upfront list of the `@tool` files in the named target.

    The upfront scan needs the typed target, which only the slash-command
    (UserPromptExpansion) path carries in command_args. Model invocation via the
    Skill tool has no target, so it just arms the per-file Read detector.
    """
    session_id = event.get("session_id", "")
    is_expansion = event.get("hook_event_name") == "UserPromptExpansion"
    if is_expansion:
        name = event.get("command_name", "") or ""
    else:  # PostToolUse on the Skill tool
        name = (event.get("tool_input") or {}).get("skill", "") or ""
    if "fix-docstrings" not in name:
        return
    open(flag_path("active", session_id), "w").close()

    if not is_expansion:
        return
    tool_files = scan_targets(event.get("command_args", ""), event.get("cwd", ""))
    if not tool_files:
        return

    # Pre-seed state so the Read detector won't re-flag these files.
    open(flag_path("referenced", session_id), "w").close()
    for fpath in tool_files:
        open(seen_marker(session_id, fpath), "w").close()

    reference = os.path.join(plugin_root, REFERENCE_REL)
    listed = "\n".join(f"  - {fpath}" for fpath in tool_files)
    context = (
        f"The `/fix-docstrings` target defines LangChain `@tool` functions in "
        f"these files:\n{listed}\n\nLangChain parses `@tool` docstrings to build "
        f"the tool's input schema, so standard Google-style `(type)` annotations "
        f"and rich formatting (bullets, tables, nested entries) can silently "
        f"corrupt or drop arguments. Read the LangChain tool docstring rules at "
        f"`{reference}` and apply them to every `@tool` function in those files."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptExpansion",
            "additionalContext": context,
        }
    }))


def mode_detect(event, plugin_root):
    """Flag a just-read file that defines LangChain @tool functions.

    The first such file in the session gets the full pointer to the reference;
    every later file gets a light reminder, since the reference is already in
    context. Each file is flagged at most once — re-reads stay silent.
    """
    session_id = event.get("session_id", "")
    if not os.path.exists(flag_path("active", session_id)):
        return

    file_path = (event.get("tool_input") or {}).get("file_path", "") or ""
    if not file_path.endswith(".py"):
        return
    seen = seen_marker(session_id, file_path)
    if os.path.exists(seen):
        return
    if not is_tool_file(file_path):
        return

    open(seen, "w").close()
    referenced = flag_path("referenced", session_id)
    if os.path.exists(referenced):
        context = (
            f"`{file_path}` also defines LangChain `@tool` functions. Apply the "
            f"parser-safe docstring rules already in context (omit `(type)`, keep "
            f"descriptions as plain prose, no bullets/tables/nested entries) to "
            f"its `@tool` functions — no need to re-read the reference."
        )
    else:
        open(referenced, "w").close()
        reference = os.path.join(plugin_root, REFERENCE_REL)
        context = (
            f"`{file_path}` defines LangChain `@tool` functions. LangChain parses "
            f"these docstrings to build the tool's input schema, so the standard "
            f"Google-style `(type)` annotations and rich formatting (bullets, "
            f"tables, nested entries) can silently corrupt or drop arguments. "
            f"Before fixing any docstrings in this file, read the LangChain tool "
            f"docstring rules at `{reference}` and apply them to every `@tool` "
            f"function. The same rules apply to any other `@tool` files in this run."
        )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    plugin_root = (
        sys.argv[2] if len(sys.argv) > 2 else os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    )
    event = read_event()
    if mode == "trigger":
        mode_trigger(event, plugin_root)
    elif mode == "detect":
        mode_detect(event, plugin_root)


if __name__ == "__main__":
    main()
