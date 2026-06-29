# LangChain Tool Docstring Rules

When a function's docstring is parsed by LangChain's tool system (the `@tool` decorator, or `StructuredTool.from_function(..., parse_docstring=True)`), extra constraints apply on top of Google style. Google style already omits types from `Args`/`Returns` for annotated code; LangChain hardens that into a rule and adds formatting-safety requirements. These rules prevent parsing failures and keep tool descriptions clean.

## Detection Patterns

Apply these rules when you see any of:

- **`@tool` decorator** on the function (enables docstring parsing by default)
- **`StructuredTool.from_function(..., parse_docstring=True)`** referencing the function
- Any code path where `parse_docstring=True` flows through to `create_schema_from_function`

If the function is clearly wired as a LangChain tool but you're unsure about `parse_docstring`, apply these rules. Omitting types from a docstring that isn't parsed is harmless, but including types in one that IS parsed risks breaking tool functionality.

## Core Rule: Omit Types from Args and Returns

LangChain's docstring parser extracts argument descriptions and discards type annotations — it reads types from the function's signature and type hints instead. Including `(type)` in Args or type prefixes in Returns adds no value and risks corrupting parsed output, particularly with complex types like `dict[str, list[int]]` where nested brackets can confuse the parser's parenthesis matching.

### Risky — types written into the docstring:

```python
"""Search for documents matching a query.

Args:
    query (str): The search query to execute.
    limit (int): Maximum number of results. Defaults to 10.
    filters (dict[str, Any]): Optional filters to narrow results.

Returns:
    list[dict]: Matching documents with relevance scores.
"""
```

### Correct — types omitted (the parser reads them from the signature):

```python
"""Search for documents matching a query.

Args:
    query: The search query to execute.
    limit: Maximum number of results. Defaults to 10.
    filters: Optional filters to narrow results.

Returns:
    Matching documents with relevance scores.
"""
```

## Formatting Safety

LangChain's parser (`_infer_arg_descriptions`) determines where one argument's description ends and the next begins using indentation and naming patterns. Complex formatting inside a description can break this boundary detection, causing arguments to be silently misparsed, merged together, or dropped.

### Rules

- Keep argument descriptions as **continuous prose** — no bullet lists, no tables, no block formatting
- Continuation lines must be **plain indented text** aligned with the description start
- Do not start continuation lines with patterns that resemble new entries: `word:` or `- item`

### BAD — bullets break argument boundary detection:

```python
@tool
def process_data(mode: str, limit: int = 10) -> dict:
    """Process data with the specified mode.

    Args:
        mode: The processing mode.
            - "fast": Skip validation
            - "strict": Full validation
            - "balanced": Selective validation
        limit: Max results.
    """
```

### GOOD — same information as inline prose:

```python
@tool
def process_data(mode: str, limit: int = 10) -> dict:
    """Process data with the specified mode.

    Args:
        mode: The processing mode. Use "fast" to skip validation,
              "strict" for full validation, or "balanced" for
              selective validation.
        limit: Maximum number of results. Defaults to 10.
    """
```

### BAD — continuation looks like a new parameter:

```python
    Args:
        config: The configuration dictionary.
            name: The name field is required.
            timeout: Controls request timeout.
        verbose: Enable verbose output.
```

### GOOD — describe structure in prose:

```python
    Args:
        config: The configuration dictionary. Must contain a "name"
                field (required) and may include a "timeout" field
                to control request timeout.
        verbose: Whether to enable verbose output.
```

## Complete Example

```python
@tool
def search_documents(
    query: str,
    collection: str = "default",
    limit: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[dict]:
    """Search for documents matching a query in the specified collection.

    Performs semantic search against the document store and returns
    ranked results with relevance scores.

    Args:
        query: The search query to execute. Supports natural language
               queries and quoted phrases for exact matching.
        collection: The document collection to search. Defaults to
                    "default".
        limit: Maximum number of results to return. Defaults to 10.
        filters: Optional key-value filters to narrow results. Keys
                 are field names, values are the required field values.

    Returns:
        Matching documents sorted by relevance score, each containing
        the document content, metadata, and match score.
    """
```
