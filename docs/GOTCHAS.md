# Potential Gotchas & Subtleties

## 1. Vector Dimensions

- **Gotcha**: We strictly use **1024 dimensions** (`BAAI/bge-m3`).
- **Risk**: If you switch models to `all-MiniLM-L6-v2` (384d) without re-indexing, Qdrant queries will fail (dimension mismatch).
- **Fix**: Update `embedding.py` AND drop/recreate the collection via `nuke_data.py`.

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
- **Fix**: Use `localhost` for host scripts, but `db` (service name) for inter-container comms.

## 6. Container ↔ Host Sync (CRITICAL)

- **Gotcha**: The Docker container filesystem and host filesystem can **diverge silently**. The container image was built at a point in time — any test files, scripts, or docs added on the host after the build won't exist in the container, and vice versa.
- **Risk**: Test counts don't match. Edits made inside the container are lost when it restarts. Documentation references files that don't exist in one environment.
- **Rule**: **Host git repo = single source of truth.** The container is a runner, not an editor.
- **Sync Protocol**:
  1. **Always edit on the host first** (or via your IDE)
  2. Push to container: `docker cp host/path/. container:/app/path/`
  3. After editing inside the container, **always sync back**: `docker cp container:/app/path/. host/path/`
  4. **Never commit inside the container** — commit on the host
  5. Verify sync: compare `ls tests/unit/test_*.py | wc -l` on both sides

```powershell
# Quick sync verification (run from host)
$hCount = (Get-ChildItem tests\unit -Filter "test_*.py" -File).Count
$cCount = docker exec claude-memory-mcp-dashboard-1 sh -c "ls /app/tests/unit/test_*.py | wc -l"
Write-Host "Host=$hCount Container=$cCount $(if($hCount -eq $cCount){'✅ IN SYNC'}else{'❌ DIVERGED'})"
```
