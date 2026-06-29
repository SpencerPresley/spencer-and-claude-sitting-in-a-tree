# fix-docstrings

Audits Python files for [Google-style](https://google.github.io/styleguide/pyguide.html) docstring compliance and fixes the violations — missing summaries, wrong section order, undocumented parameters, malformed `Args`/`Returns`/`Raises` sections.

Types are intentionally omitted from `Args` and `Returns`: they come from the function's annotations, and the IDE already surfaces the signature on hover. A type is only written into the docstring when the parameter or return value has no annotation — matching the Google style guide's own rule.

## How it works

- The `fix-docstrings` skill is the entry point. Point it at a file or directory; it scans every module, class, function, and method and applies the style reference inline.
- A hook (`hooks/scripts/langchain_tool_context.py`) adds the one piece of context the skill body deliberately leaves out: **LangChain `@tool` docstrings parse differently.** LangChain reads the docstring to build a tool's input schema, so `(type)` annotations and rich formatting (bullets, tables, nested entries) can silently corrupt or drop arguments.

  Rather than carry that caveat in the skill for every run, the hook injects it only when it's relevant:

  1. When the skill is invoked — whether you type `/fix-docstrings` (a `UserPromptExpansion` hook) or the model invokes the skill itself (a `PostToolUse` hook on the `Skill` tool) — a per-session flag is set. On the `/fix-docstrings <target>` path the typed target is available, so the hook **scans it up front** and, if any files in it define `@tool` functions, injects the exact list along with the pointer to `references/langchain-tool-docstrings.md`. You learn which files need parser-safe rules before editing any of them.
  2. For everything the upfront scan can't see — the model invoking the skill (no target), or a file read from outside the named target — a `PostToolUse` hook on `Read` is the fallback. It checks each Python file the skill opens and injects the parser-safe rules graduated to avoid wasted tokens: the **first** `@tool` file in the session gets the full pointer; every **later** one gets a light reminder to apply the rules already in context (no re-read). Each file is flagged at most once.

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
