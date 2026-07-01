#!/usr/bin/env python3
"""Discover CLAUDE.md files in directories outside the project tree.

Claude Code PostToolUse hook that reads JSON hook input from stdin.
Outputs discovery messages to stderr and exits 2 to feed them back
to Claude.
"""

import json
import os
import re
import shlex
import sys


def extract_structured_path(tool_name: str, tool_input: dict) -> str | None:
    """Extract target path from tools with structured path fields.

    Args:
        tool_name (str): Name of the tool (e.g. `Read`, `Edit`, `Glob`).
        tool_input (dict): The tool's input payload.

    Returns:
        str | None: The file path from the tool input, or `None` if the
                    tool is not recognized or the field is missing.
    """
    if tool_name in ("Read", "Edit", "Write"):
        return tool_input.get("file_path") or None
    if tool_name in ("Glob", "Grep"):
        return tool_input.get("path") or None
    return None


def extract_paths_from_bash(command: str) -> list[str]:
    """Extract candidate file paths from a bash command string.

    Uses a pipeline of extraction strategies. Add new `_extract_*`
    functions and append their results to `candidates` to expand
    coverage without rewriting existing logic.

    Args:
        command (str): The raw bash command string to parse.

    Returns:
        list[str]: Absolute paths found in the command tokens.
    """
    candidates: list[str] = []
    candidates.extend(_extract_token_paths(command))
    return candidates


def _extract_token_paths(command: str) -> list[str]:
    """Find absolute paths appearing as command tokens via shlex.

    Args:
        command (str): The raw bash command string to parse.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []

    paths: list[str] = []
    for token in tokens:
        if token.startswith("/"):
            paths.append(token)
        elif token.startswith("~"):
            paths.append(os.path.expanduser(token))
    return paths


def resolve_target_path(candidates: list[str]) -> str | None:
    """Return the first candidate whose path (or parent dir) exists on disk.

    Args:
        candidates (list[str]): Absolute paths to check for existence.

    Returns:
        str | None: The first path that exists or whose parent directory
                    exists, or `None` if no candidate qualifies.
    """
    for path in candidates:
        if os.path.exists(path):
            return path

    # Fallback: accept paths whose parent exists (globs, new files, etc.)
    for path in candidates:
        parent = os.path.dirname(path)
        if parent and os.path.isdir(parent):
            return path

    return None


def config_dir() -> str:
    """Return the Claude Code config directory, canonicalized.

    Honors `CLAUDE_CONFIG_DIR`, falling back to `~/.claude`. Everything
    inside this tree is Claude Code's own config and installed plugins;
    its `CLAUDE.md` is the global user memory that Claude Code always loads
    at startup. Discovery must never resurface files from here, or touching
    any config/plugin path (which happens constantly) would nag the model
    to re-read instructions already in context.

    Returns:
        str: The absolute, symlink-resolved config directory path.
    """
    raw = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude"
    )
    return os.path.realpath(raw).rstrip("/") or "/"


def get_target_directory(tool_name: str, tool_input: dict) -> str | None:
    """Determine the target directory for a tool invocation.

    Args:
        tool_name (str): Name of the tool being invoked.
        tool_input (dict): The tool's input payload.

    Returns:
        str | None: The directory containing the target path, or `None`
                    if no valid path can be determined.
    """
    target = extract_structured_path(tool_name, tool_input)

    if target is None and tool_name == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return None
        candidates = extract_paths_from_bash(command)
        target = resolve_target_path(candidates)

    if not target:
        return None

    if os.path.isdir(target):
        return target
    return os.path.dirname(target)


def discover_claude_md(
    directory: str,
    cwd: str,
    session_id: str,
) -> list[str]:
    """Walk up from `directory`, collecting undiscovered CLAUDE.md files.

    Stops at ancestors of `cwd` (already loaded at startup by Claude Code).
    Deduplicates against a session-scoped tracking file.

    Args:
        directory (str): Starting directory to walk upward from.
        cwd (str): The project working directory; traversal stops at its
                   ancestors.
        session_id (str): Unique session identifier used to scope the
                          tracking file.

    Returns:
        list[str]: Newly discovered CLAUDE.md file paths.
    """
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
    tracking_file = os.path.join(
        os.environ.get("TMPDIR", "/tmp"),
        f"claude-md-seen-{safe_id}",
    )

    seen: set[str] = set()
    if os.path.isfile(tracking_file):
        with open(tracking_file, "r") as fh:
            seen = {line.strip() for line in fh if line.strip()}

    found: list[str] = []
    current = directory

    while current != "/":
        if cwd == current or cwd.startswith(current + "/"):
            break

        claude_md = os.path.join(current, "CLAUDE.md")
        if os.path.isfile(claude_md) and claude_md not in seen:
            found.append(claude_md)
            seen.add(claude_md)

        current = os.path.dirname(current)

    if found:
        with open(tracking_file, "a") as fh:
            for path in found:
                fh.write(path + "\n")
        os.chmod(tracking_file, 0o600)

    return found


def emit_discovery(found: list[str]) -> None:
    """Write the discovery message to stderr and exit 2.

    Args:
        found (list[str]): Paths to CLAUDE.md files to report.

    Raises:
        SystemExit: Always exits with code 2 to signal Claude Code
                    to ingest the message.
    """
    file_list = "\n".join(f"  - {path}" for path in found)

    if len(found) == 1:
        message = (
            "<claude-md-discovery-extended>\n"
            "A CLAUDE.md file was discovered that you have not read this session.\n"
            "\n"
            "IMPORTANT: You MUST read it immediately.\n"
            "\n"
            "Once you have read it, continue working on your current task. "
            "IMPORTANT: Do NOT stop to inform the user you have read it.\n"
            "\n"
            f"**File Path**: {found[0]}\n"
            "</claude-md-discovery-extended>"
        )
    else:
        message = (
            "<claude-md-discovery-extended>\n"
            f"{len(found)} CLAUDE.md files were discovered that you have not read this session.\n"
            "\n"
            "IMPORTANT: You MUST read each immediately.\n"
            "\n"
            "Once you have read each file, continue working on your current task. "
            "IMPORTANT: Do NOT stop to inform the user you have read them.\n"
            "\n"
            "**File Paths**:\n"
            f"{file_list}\n"
            "</claude-md-discovery-extended>"
        )

    print(message, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    """Entry point that wraps `_main` with a top-level exception guard."""
    try:
        _main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)


def _main() -> None:
    """Parse hook input, resolve target directory, and emit discoveries."""
    os.umask(0o077)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")
    session_id: str = data.get("session_id", "")
    cwd: str = data.get("cwd", "")
    tool_input: dict = data.get("tool_input", {})

    if not tool_name or not session_id or not cwd:
        sys.exit(0)

    # Canonicalize to resolve symlinks and ".." components
    cwd = os.path.realpath(cwd).rstrip("/") or "/"

    directory = get_target_directory(tool_name, tool_input)
    if not directory:
        sys.exit(0)

    directory = os.path.realpath(directory).rstrip("/") or "/"

    if directory == cwd or directory.startswith(cwd + "/"):
        sys.exit(0)

    # Never discover inside the Claude Code config dir: its CLAUDE.md is the
    # global user memory (always loaded at startup) and any plugin CLAUDE.md
    # under it is config, not a project the user is working in.
    config = config_dir()
    if directory == config or directory.startswith(config + "/"):
        sys.exit(0)

    found = discover_claude_md(directory, cwd, session_id)
    if not found:
        sys.exit(0)

    emit_discovery(found)


if __name__ == "__main__":
    main()
