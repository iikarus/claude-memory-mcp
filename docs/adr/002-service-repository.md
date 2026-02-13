# ADR-002: Service-Repository Architecture

**Status:** Accepted
**Date:** 2026-01-06
**Context:** The codebase needs a clean separation between MCP tool handlers, business logic, and data access.
**Decision:** Adopt a three-layer architecture:

1. **Tools** (`server.py`, `tools_extra.py`) — MCP interface, parameter validation
2. **Services** (`MemoryService`, `ClusteringService`) — business logic orchestration
3. **Repositories** (`repository_queries.py`, `repository_traversal.py`, `vector_store.py`) — data access

**Consequences:**

- Each layer is independently testable with mocking.
- New tools can be added without touching data access code.
- 460+ unit tests validate all layers in isolation.
