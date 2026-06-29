#!/usr/bin/env python3
"""Capture the raw stdin payload a hook receives and dump it to tests/outputs/.

This is throwaway test instrumentation for discovering the exact JSON shape
Claude Code hands to each hook event — in particular the `command_name` that
`UserPromptExpansion` reports for a plugin/skill slash command, and the
`tool_input.skill` that `PostToolUse` reports for the Skill tool. Those values
are undocumented, so we observe them directly instead of guessing the matcher.

The hook stays out of the model's way: it records the payload and exits 0 with
no stdout, so it never blocks an expansion or injects context.

Output files: tests/outputs/<label>__<event>__<discriminator>__<pid>_<ns>.json
The label comes from the CAPTURE_LABEL env var so the runner can tag which
scenario (manual vs model invocation) produced each capture.
"""
import json
import os
import re
import sys
import time

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def slug(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:60] or "none"


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        event = {"_unparsed_stdin": raw}

    hook_event = event.get("hook_event_name", "unknown")
    # A human-readable discriminator per event type.
    if hook_event == "UserPromptExpansion":
        discriminator = event.get("command_name", "no-command")
    elif "tool_name" in event:
        discriminator = event.get("tool_name", "no-tool")
        if event.get("tool_name") == "Skill":
            skill = (event.get("tool_input") or {}).get("skill", "")
            discriminator = f"Skill-{skill}"
    else:
        discriminator = "event"

    label = os.environ.get("CAPTURE_LABEL", "run")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name = f"{slug(label)}__{slug(hook_event)}__{slug(discriminator)}__{os.getpid()}_{time.time_ns()}.json"
    with open(os.path.join(OUTPUT_DIR, name), "w", encoding="utf-8") as handle:
        json.dump(event, handle, indent=2, sort_keys=True)

    # Stay silent: no decision, no additionalContext — just observe.
    sys.exit(0)


if __name__ == "__main__":
    main()
