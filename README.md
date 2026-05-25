# simple-but-powerful

Focused Claude Code plugins that each solve one specific problem. Small enough to actually use, sharp enough to actually help.

## Installation

```text
/plugin marketplace add SpencerPresley/simple-but-powerful
```

Then install individual plugins:

```text
/plugin install <plugin-name>@simple-but-powerful
```

## Plugins

| Plugin | What it does |
|--------|-------------|
| [claude-md-discovery-extended](plugins/claude-md-discovery-extended/) | Auto-discovers and loads CLAUDE.md files from any directory outside your project tree when the model accesses files there. |
| [codex-context-loader](plugins/codex-context-loader/) | Injects a detailed Codex-plugin briefing into your session — but only when the Codex plugin is actually enabled, so it costs zero context tokens when you're not using Codex. |
| [adversarial-review](plugins/adversarial-review/) | An adversarial code/plan reviewer subagent that challenges the work to find the strongest reasons not to ship — reviewing only the exact slice you name. |

## License

MIT
