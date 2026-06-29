# fix-docstrings

Audits Python files for [Google-style](https://google.github.io/styleguide/pyguide.html) docstring compliance and fixes the violations — missing summaries, wrong section order, undocumented parameters, malformed `Args`/`Returns`/`Raises` sections.

Types are intentionally omitted from `Args` and `Returns`: they come from the function's annotations, and the IDE already surfaces the signature on hover. A type is only written into the docstring when the parameter or return value has no annotation — matching the Google style guide's own rule.

## How it works

- The `fix-docstrings` skill is the entry point. Point it at a file or directory; it scans every module, class, function, and method and applies the style reference inline.
- A hook (`hooks/scripts/langchain_tool_context.py`) adds the one piece of context the skill body deliberately leaves out: **LangChain `@tool` docstrings parse differently.** LangChain reads the docstring to build a tool's input schema, so `(type)` annotations and rich formatting (bullets, tables, nested entries) can silently corrupt or drop arguments.

  Rather than carry that caveat in the skill for every run, the hook injects it only when it's relevant:

  1. When the skill is invoked — whether you type `/fix-docstrings` (a `UserPromptExpansion` hook) or the model invokes the skill itself (a `PostToolUse` hook on the `Skill` tool) — a per-session flag is set.
  2. While that flag is set, a `PostToolUse` hook on `Read` checks each Python file the skill opens. If a file defines `@tool` functions *and* imports LangChain, the hook injects a pointer to `references/langchain-tool-docstrings.md` and tells the model to apply those parser-safe rules to that file — then latches so it fires at most once per run.

  When you're not fixing LangChain tools, the reference is never loaded and the caveat never enters context.

## Usage

```
/fix-docstrings <file or directory path>
```

Or in conversation: "fix the docstrings in `src/tools/`".

For a directory it processes `__init__.py` files first, then modules, then tests (with lighter requirements), batching large directories and confirming before continuing.

## Layout

```
fix-docstrings/
  skills/fix-docstrings/
    SKILL.md                              # style reference + execution process
    references/langchain-tool-docstrings.md  # parser-safe rules (loaded by the hook)
  hooks/
    hooks.json
    scripts/langchain_tool_context.py     # detects @tool files, injects the reference
```

## Requirements

The hook runs on `python3` (standard library only) and is silent if it isn't present.
