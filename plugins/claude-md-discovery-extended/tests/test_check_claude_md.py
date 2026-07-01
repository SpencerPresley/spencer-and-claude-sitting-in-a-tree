"""Tests for check_claude_md.py hook script.

Mirrors the existing bats test suite and adds Bash-specific tests.
Run with: python3 -m pytest python-version/tests/ -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(
    Path(__file__).resolve().parent.parent / "hooks" / "scripts" / "check_claude_md.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_hook(payload: dict, env: dict | None = None) -> tuple[int, str, str]:
    """Run the hook script with *payload* as JSON on stdin.

    Args:
        payload (dict): The hook input serialized to stdin.
        env (dict | None): Environment for the subprocess. When ``None``
            the parent environment is inherited unchanged.

    Returns (exit_code, stdout, stderr).
    """
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


_sid_counter = 0


def next_sid(label: str = "") -> str:
    global _sid_counter
    _sid_counter += 1
    return f"pytest-{label}-{_sid_counter}-{os.getpid()}"


def build_json(
    *,
    tool: str,
    sid: str,
    cwd: str,
    file_path: str = "",
    path: str = "",
    command: str = "",
) -> dict:
    return {
        "tool_name": tool,
        "session_id": sid,
        "cwd": cwd,
        "tool_input": {
            "file_path": file_path,
            "path": path,
            "command": command,
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def layout(tmp_path):
    """Create test directory layout:

    tmp/workspace/project/              (cwd)
    tmp/workspace/project/subdir/
    tmp/workspace/sibling/              CLAUDE.md
    tmp/workspace/sibling/deep/nested/  CLAUDE.md
    tmp/workspace/tools/linter/         CLAUDE.md  (cousin)
    tmp/workspace/                      CLAUDE.md  (ancestor of cwd)
    tmp/other-team/services/api/        CLAUDE.md  (unrelated tree)
    """
    project = tmp_path / "workspace" / "project"
    sibling = tmp_path / "workspace" / "sibling"
    deep = sibling / "deep" / "nested"
    cousin = tmp_path / "workspace" / "tools" / "linter"
    unrelated = tmp_path / "other-team" / "services" / "api"

    (project / "subdir").mkdir(parents=True)
    deep.mkdir(parents=True)
    cousin.mkdir(parents=True)
    unrelated.mkdir(parents=True)

    (sibling / "CLAUDE.md").write_text("# sibling\n")
    (tmp_path / "workspace" / "CLAUDE.md").write_text("# parent\n")
    (deep / "CLAUDE.md").write_text("# deep\n")
    (cousin / "CLAUDE.md").write_text("# cousin\n")
    (unrelated / "CLAUDE.md").write_text("# unrelated\n")

    return {
        "project": str(project),
        "sibling": str(sibling),
        "deep": str(deep),
        "cousin": str(cousin),
        "unrelated": str(unrelated),
        "parent": str(tmp_path / "workspace"),
    }


@pytest.fixture(autouse=True)
def cleanup_tracking():
    """Remove any tracking files created during tests."""
    yield
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    for name in os.listdir(tmpdir):
        if name.startswith("claude-md-seen-pytest-"):
            os.unlink(os.path.join(tmpdir, name))


# ---------------------------------------------------------------------------
# Basic validation (mirrors bats tests)
# ---------------------------------------------------------------------------

class TestBasicValidation:
    def test_exits_0_on_empty_json(self):
        rc, _, _ = run_hook({})
        assert rc == 0

    def test_exits_0_when_tool_name_missing(self):
        rc, _, _ = run_hook({"session_id": "x", "cwd": "/tmp", "tool_input": {}})
        assert rc == 0

    def test_exits_0_when_session_id_missing(self):
        rc, _, _ = run_hook({"tool_name": "Read", "cwd": "/tmp", "tool_input": {}})
        assert rc == 0

    def test_exits_0_when_cwd_missing(self):
        rc, _, _ = run_hook({"tool_name": "Read", "session_id": "x", "tool_input": {}})
        assert rc == 0

    def test_exits_0_for_unknown_tool_type(self, layout):
        sid = next_sid("unknown")
        payload = build_json(tool="SomeUnknownTool", sid=sid, cwd=layout["project"])
        rc, _, _ = run_hook(payload)
        assert rc == 0

    def test_exits_0_when_file_path_empty(self, layout):
        sid = next_sid("empty-fp")
        payload = build_json(tool="Read", sid=sid, cwd=layout["project"], file_path="")
        rc, _, _ = run_hook(payload)
        assert rc == 0

    def test_exits_0_when_path_empty_for_glob(self, layout):
        sid = next_sid("empty-path")
        payload = build_json(tool="Glob", sid=sid, cwd=layout["project"], path="")
        rc, _, _ = run_hook(payload)
        assert rc == 0


# ---------------------------------------------------------------------------
# Project-internal files (should be skipped)
# ---------------------------------------------------------------------------

class TestSkipsProjectFiles:
    def test_skips_file_in_project_root(self, layout):
        sid = next_sid("proj-root")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["project"], "file.txt"),
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0

    def test_skips_file_in_project_subdirectory(self, layout):
        sid = next_sid("proj-sub")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["project"], "subdir", "file.txt"),
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0


# ---------------------------------------------------------------------------
# Ancestor stopping
# ---------------------------------------------------------------------------

class TestAncestorStopping:
    def test_stops_walk_at_ancestor_of_cwd(self, layout):
        sid = next_sid("ancestor")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["deep"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0


# ---------------------------------------------------------------------------
# Discovery (structured tools)
# ---------------------------------------------------------------------------

class TestDiscovery:
    def test_discovers_sibling_claude_md(self, layout):
        sid = next_sid("sibling")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr

    def test_excludes_ancestor_claude_md(self, layout):
        sid = next_sid("no-ancestor")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        _, _, stderr = run_hook(payload)
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr
        assert os.path.join(layout["parent"], "CLAUDE.md") not in stderr

    def test_discovers_multiple_walking_up(self, layout):
        sid = next_sid("multi")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["deep"], "file.txt"),
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["deep"], "CLAUDE.md") in stderr
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr

    def test_discovers_cousin_claude_md(self, layout):
        sid = next_sid("cousin")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["cousin"], "file.txt"),
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["cousin"], "CLAUDE.md") in stderr

    def test_discovers_unrelated_tree_claude_md(self, layout):
        sid = next_sid("unrelated")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["unrelated"], "file.txt"),
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["unrelated"], "CLAUDE.md") in stderr

    def test_unrelated_tree_excludes_ancestor_claude_md(self, layout):
        sid = next_sid("unrelated-no-ancestor")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["unrelated"], "file.txt"),
        )
        _, _, stderr = run_hook(payload)
        assert os.path.join(layout["parent"], "CLAUDE.md") not in stderr

    def test_no_discovery_when_no_claude_md(self, layout):
        os.unlink(os.path.join(layout["sibling"], "CLAUDE.md"))
        sid = next_sid("no-cmd")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0


# ---------------------------------------------------------------------------
# Tool-specific path extraction
# ---------------------------------------------------------------------------

class TestToolExtraction:
    @pytest.mark.parametrize("tool", ["Read", "Edit", "Write"])
    def test_file_path_tools(self, layout, tool):
        sid = next_sid(f"tool-{tool}")
        payload = build_json(
            tool=tool, sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc, _, _ = run_hook(payload)
        assert rc == 2

    @pytest.mark.parametrize("tool", ["Glob", "Grep"])
    def test_path_tools(self, layout, tool):
        sid = next_sid(f"tool-{tool}")
        payload = build_json(
            tool=tool, sid=sid, cwd=layout["project"],
            path=layout["sibling"],
        )
        rc, _, _ = run_hook(payload)
        assert rc == 2


# ---------------------------------------------------------------------------
# Bash tool path extraction
# ---------------------------------------------------------------------------

class TestBashExtraction:
    def test_simple_cat(self, layout):
        target = os.path.join(layout["sibling"], "CLAUDE.md")
        sid = next_sid("bash-cat")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command=f"cat {target}",
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr

    def test_ls_directory(self, layout):
        sid = next_sid("bash-ls")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command=f"ls {layout['sibling']}",
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr

    def test_multiple_paths_picks_first_valid(self, layout):
        sid = next_sid("bash-multi")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command=f"cp {layout['sibling']}/file.txt /nonexistent/place",
        )
        rc, _, stderr = run_hook(payload)
        # Should discover via sibling path (first valid)
        assert rc == 2
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr

    def test_no_paths_in_command(self, layout):
        sid = next_sid("bash-nopath")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command="echo hello world",
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0

    def test_empty_command(self, layout):
        sid = next_sid("bash-empty")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command="",
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0

    def test_quoted_path(self, layout):
        # Create a directory with a space in the name
        spaced = os.path.join(layout["parent"], "dir with spaces")
        os.makedirs(spaced, exist_ok=True)
        Path(os.path.join(spaced, "CLAUDE.md")).write_text("# spaced\n")

        sid = next_sid("bash-quoted")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command=f'cat "{spaced}/file.txt"',
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(spaced, "CLAUDE.md") in stderr

    def test_tilde_expansion(self, layout):
        # This test just verifies tilde paths are expanded; discovery
        # depends on whether ~/... has a CLAUDE.md, so we just check
        # it doesn't crash
        sid = next_sid("bash-tilde")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command="cat ~/somefile.txt",
        )
        rc, _, _ = run_hook(payload)
        assert rc in (0, 2)  # either is fine

    def test_malformed_quotes_dont_crash(self, layout):
        sid = next_sid("bash-malformed")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command="echo 'unterminated",
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0

    def test_bash_targets_project_dir_skipped(self, layout):
        sid = next_sid("bash-proj")
        payload = build_json(
            tool="Bash", sid=sid, cwd=layout["project"],
            command=f"cat {layout['project']}/file.txt",
        )
        rc, _, _ = run_hook(payload)
        assert rc == 0


# ---------------------------------------------------------------------------
# Session deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_second_call_dedupes(self, layout):
        sid = next_sid("dedup")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc1, _, _ = run_hook(payload)
        assert rc1 == 2

        rc2, _, _ = run_hook(payload)
        assert rc2 == 0

    def test_different_sessions_report_independently(self, layout):
        sid1 = next_sid("indep1")
        sid2 = next_sid("indep2")
        payload1 = build_json(
            tool="Read", sid=sid1, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        payload2 = build_json(
            tool="Read", sid=sid2, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc1, _, _ = run_hook(payload1)
        rc2, _, _ = run_hook(payload2)
        assert rc1 == 2
        assert rc2 == 2


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_stderr_contains_xml_tags(self, layout):
        sid = next_sid("xml")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        _, _, stderr = run_hook(payload)
        assert "<claude-md-discovery-extended>" in stderr
        assert "</claude-md-discovery-extended>" in stderr

    def test_stderr_lists_paths(self, layout):
        sid = next_sid("paths")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        _, _, stderr = run_hook(payload)
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_root_path(self, layout):
        sid = next_sid("root")
        payload = build_json(
            tool="Read", sid=sid, cwd=layout["project"],
            file_path="/somefile.txt",
        )
        rc, _, _ = run_hook(payload)
        assert rc in (0, 2)

    def test_cwd_at_root(self, layout):
        sid = next_sid("cwd-root")
        payload = build_json(
            tool="Read", sid=sid, cwd="/",
            file_path=os.path.join(layout["sibling"], "file.txt"),
        )
        rc, _, _ = run_hook(payload)
        assert rc in (0, 2)

    def test_target_is_directory(self, layout):
        sid = next_sid("dir-target")
        payload = build_json(
            tool="Glob", sid=sid, cwd=layout["project"],
            path=layout["sibling"],
        )
        rc, _, stderr = run_hook(payload)
        assert rc == 2
        assert os.path.join(layout["sibling"], "CLAUDE.md") in stderr


# ---------------------------------------------------------------------------
# Config-directory exclusion
#
# `${CLAUDE_CONFIG_DIR:-~/.claude}` holds Claude Code's own config and
# installed plugins. Its `CLAUDE.md` is the global user memory that Claude
# Code always loads at startup, so discovery must never resurface anything
# inside that tree -- otherwise touching any config/plugin file (which
# happens constantly) nags the model to re-read files already in context.
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_layout(tmp_path):
    """Create a project cwd and a separate Claude config dir tree.

    tmp/workspace/project/                 (cwd, outside config)
    tmp/workspace/sibling/                 CLAUDE.md (legit discovery)
    tmp/cfghome/.claude/                   CLAUDE.md (global user memory)
    tmp/cfghome/.claude/plugins/foo/       CLAUDE.md (plugin ships its own)
    tmp/cfghome/.claude/plugins/foo/hooks/
    """
    project = tmp_path / "workspace" / "project"
    sibling = tmp_path / "workspace" / "sibling"
    config = tmp_path / "cfghome" / ".claude"
    plugin_hooks = config / "plugins" / "foo" / "hooks"

    project.mkdir(parents=True)
    sibling.mkdir(parents=True)
    plugin_hooks.mkdir(parents=True)

    (sibling / "CLAUDE.md").write_text("# sibling\n")
    (config / "CLAUDE.md").write_text("# global user memory\n")
    (config / "plugins" / "foo" / "CLAUDE.md").write_text("# plugin repo\n")

    return {
        "project": str(project),
        "sibling": str(sibling),
        "config": str(config),
        "plugin": str(config / "plugins" / "foo"),
        "plugin_hooks": str(plugin_hooks),
    }


def config_env(config_dir: str) -> dict:
    """Parent environment with CLAUDE_CONFIG_DIR pinned to *config_dir*."""
    return {**os.environ, "CLAUDE_CONFIG_DIR": config_dir}


class TestConfigDirExclusion:
    def test_global_memory_not_reported(self, config_layout):
        # Reading a config file (e.g. settings.json) must not resurface
        # the global-memory CLAUDE.md sitting beside it.
        sid = next_sid("cfg-global")
        payload = build_json(
            tool="Read", sid=sid, cwd=config_layout["project"],
            file_path=os.path.join(config_layout["config"], "settings.json"),
        )
        rc, _, stderr = run_hook(payload, env=config_env(config_layout["config"]))
        assert rc == 0
        assert "CLAUDE.md" not in stderr

    def test_plugin_claude_md_under_config_not_reported(self, config_layout):
        # A plugin that ships its own CLAUDE.md inside the config tree
        # must not be flagged when the model reads that plugin's files.
        sid = next_sid("cfg-plugin")
        payload = build_json(
            tool="Read", sid=sid, cwd=config_layout["project"],
            file_path=os.path.join(config_layout["plugin_hooks"], "script.py"),
        )
        rc, _, stderr = run_hook(payload, env=config_env(config_layout["config"]))
        assert rc == 0
        assert "CLAUDE.md" not in stderr

    def test_bash_touching_config_path_not_reported(self, config_layout):
        # The common real-world trigger: a Bash command that merely names
        # a path inside the config dir (find/grep/ls over ~/.claude).
        sid = next_sid("cfg-bash")
        payload = build_json(
            tool="Bash", sid=sid, cwd=config_layout["project"],
            command=f"find {config_layout['config']} -name script.py",
        )
        rc, _, stderr = run_hook(payload, env=config_env(config_layout["config"]))
        assert rc == 0
        assert "CLAUDE.md" not in stderr

    def test_sibling_still_discovered_with_config_dir_set(self, config_layout):
        # Guard against over-exclusion: a genuine sibling outside the
        # config tree must still be discovered while CLAUDE_CONFIG_DIR is set.
        sid = next_sid("cfg-sibling-ok")
        payload = build_json(
            tool="Read", sid=sid, cwd=config_layout["project"],
            file_path=os.path.join(config_layout["sibling"], "file.txt"),
        )
        rc, _, stderr = run_hook(payload, env=config_env(config_layout["config"]))
        assert rc == 2
        assert os.path.join(config_layout["sibling"], "CLAUDE.md") in stderr
