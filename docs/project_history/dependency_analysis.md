# Dependency Analysis (Final Audit)

**Status**: Highly Decoupled.

## Current Graph

```mermaid
graph TD
    claude_memory.server --> claude_memory.schema
    claude_memory.server --> claude_memory.tools
    claude_memory.tools --> claude_memory.interfaces
    claude_memory.tools --> claude_memory.repository
    claude_memory.tools --> claude_memory.schema
    claude_memory.tools --> claude_memory.embedding
    dashboard.app --> claude_memory.tools
```

## Observations

1.  **Strict Layering**: No cycles.
    - `Schema` is at the bottom (Pure Data).
    - `Repository` handles Persistence.
    - `Tools` (Service) handles Orchestration.
    - `Server` handles Protocol (MCP).
2.  **Lazy Dependency detected**: `tools --> embedding`.
    - **Why**: `MemoryService.__init__` imports `EmbeddingService` if not provided.
    - **Optimization**: To fully decouple, we can remove this default and make `server.py` and `app.py` responsible for instantiation.
    - **Benefit**: `tools.py` becomes purely abstract regarding embedding.

## Simplification Opportunities

1.  **Remove Default Embedder**: Force injection in `MemoryService`.
    - `server.py` and `dashboard/app.py` must instantiate `EmbeddingService`.
    - Result: `tools.py` no longer depends on `torch`/`sentence-transformers` _at all_, even lazily.
2.  **Mypy Strictness**:
    - The "Persistent Errors" are a conflict between `FastMCP`'s untyped decorators and strict Mypy settings.
    - **Action**: Add explicit type casts or wrapper functions to isolate untyped libs.

## Strategic Decision

> [!CHECK] **COMPLETED**: Simplification #1 Executed.
> We have successfully severed the hard dependency between `tools` and `embedding`.
> `MemoryService` now requires dependency injection.
> `tools.py` is now pure orchestration logic with zero ML dependencies.

## Resulting Graph (Current State)

```mermaid
graph TD
    claude_memory.server --> claude_memory.schema
    claude_memory.server --> claude_memory.tools
    claude_memory.server --> claude_memory.embedding
    claude_memory.tools --> claude_memory.interfaces
    claude_memory.tools --> claude_memory.repository
    claude_memory.tools --> claude_memory.schema
    dashboard.app --> claude_memory.tools
    dashboard.app --> claude_memory.embedding
```

**Key Change:** `claude_memory.tools` NO LONGER depends on `claude_memory.embedding`.

- `embedding` is injected from `server` or `app`.
- This ensures the core logic remains lightweight and testable without Torch overhead.
