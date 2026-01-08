# Potential Gotchas & Subtleties

## 1. Vector Dimensions

- **Gotcha**: We strictly use **1024 dimensions** (`BAAI/bge-m3`).
- **Risk**: If you switch models to `all-MiniLM-L6-v2` (384d) without re-indexing, FalkorDB queries will fail or return garbage.
- **Fix**: Update `embedding.py` AND drop/recreate the index in `repository.py`.

## 2. Pydantic & Enums

- **Gotcha**: `node_type` is validated against a Literal list (Project, Entity, Concept, etc.).
- **Risk**: Passing "Note" or "Task" will raise a Validation Error.
- **Fix**: Update `schema.py` to allow new types.

## 3. Mypy & Decorators

- **Gotcha**: The `@mcp.tool()` decorator in `server.py` often confuses Mypy, leading to "Untyped decorator" errors.
- **Risk**: Pre-commit failure.
- **Fix**: We use `# type: ignore[misc]` on these decorators. Do not remove unless `fastmcp` updates their typing.

## 4. Lazy Loading

- **Gotcha**: `EmbeddingService` loads the model (~500MB) on first use.
- **Risk**: First request latency is high (3-5s).
- **Fix**: This is by design to speed up CLI startup. Docker containers might need more RAM (2GB+ recommended).

## 5. Docker Networking

- **Gotcha**: When running in Docker, `localhost` inside the container ! = `localhost` on host.
- **Risk**: `operations.py` running locally might not reach the Docker DB.
- **Fix**: Use `localhost` for host scripts, but `db` (service name) for inter-container comma.
