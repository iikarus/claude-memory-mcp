# Potential Gotchas & Subtleties

## 1. Vector Dimensions

- **Gotcha**: We strictly use **1024 dimensions** (`BAAI/bge-m3`).
- **Risk**: If you switch models to `all-MiniLM-L6-v2` (384d) without re-indexing, Qdrant queries will fail (dimension mismatch).
- **Fix**: Update `embedding.py` AND drop/recreate the collection via `nuke_data.py`.

## 2. Pydantic & Enums

- **Gotcha**: `node_type` is validated against a Literal list (Project, Entity, Concept, etc.).
- **Risk**: Passing "Note" or "Task" will raise a Validation Error.
- **Fix**: Update `schema.py` to allow new types, or use `create_memory_type()` for runtime extensions.

## 3. Docker Networking (`QDRANT_HOST`)

- **Gotcha**: Inside Docker containers, `localhost` points to the container itself, not the host machine.
- **Risk**: If `QDRANT_HOST` is not set to `qdrant` (the service name), vector operations silently fail to connect.
- **Fix**: The `docker-compose.yml` sets `QDRANT_HOST=qdrant` and `FALKORDB_HOST=graphdb` for all services. Do not remove these.

## 4. Qdrant Healthcheck (No curl/wget)

- **Gotcha**: The `qdrant/qdrant` Docker image has no `curl` or `wget`.
- **Risk**: Standard HTTP healthchecks fail with "exec not found".
- **Fix**: We use `bash -c 'echo > /dev/tcp/localhost/6333'` — bash's built-in TCP probe. Do not change to curl.

## 5. cp1252 Encoding (Windows headless)

- **Gotcha**: Python on Windows defaults to cp1252 encoding when running headless (Task Scheduler, subprocess).
- **Risk**: Scripts with emoji/unicode output (`💾`, `✅`) crash with `UnicodeEncodeError`.
- **Fix**: Set `PYTHONUTF8=1` env var in subprocess calls. See `scheduled_backup.py` for the pattern.

## 6. Lazy Loading

- **Gotcha**: `EmbeddingService` loads the model (~500MB) on first use.
- **Risk**: First request latency is high (3-5s).
- **Fix**: This is by design to speed up CLI startup. Docker containers might need more RAM (2GB+ recommended).

## 7. `_ensure_collection` Re-raises

- **Gotcha**: `vector_store.py` re-raises exceptions after logging (previously swallowed silently).
- **Risk**: If Qdrant is down, callers will see the error immediately instead of getting silent `None` results.
- **Fix**: This is intentional — the `@retry_on_transient` decorator handles reconnection. Do not add bare `except` blocks.

## 8. `get_all_nodes` Query

- **Gotcha**: The query is `MATCH (n:Entity) RETURN n`. There is no `WHERE n.embedding IS NOT NULL` filter.
- **Risk**: If you re-add an embedding filter, the Librarian will get zero results (embeddings live in Qdrant, not on graph nodes).
- **Fix**: Never filter nodes by `embedding` property in Cypher. Qdrant is the vector authority.

## 9. Docker Build Context

- **Gotcha**: Without `.dockerignore`, the entire project (~1.6 GB including `.tox`, caches) gets sent to Docker.
- **Risk**: 3-hour builds instead of 3-minute builds.
- **Fix**: `.dockerignore` excludes development artifacts. Keep it updated if adding new large directories.

## 10. Temporal Edge Direction

- **Gotcha**: `PRECEDED_BY` edges point **backward** (newer → older).
- **Risk**: If you query `get_temporal_neighbors(id, direction="after")`, you traverse **incoming** edges, not outgoing.
- **Fix**: Read `repository.py` — `direction="before"` follows outgoing PRECEDED_BY, `"after"` follows incoming.

## 11. Salience Is Fire-and-Forget

- **Gotcha**: Salience updates run asynchronously via `asyncio.create_task()` after search.
- **Risk**: If FalkorDB is slow, the salience update may fail silently. The warning `"Background salience update failed"` is logged but does not block search.
- **Fix**: This is by design. The `@retry_on_transient` decorator handles transient failures. Salience is eventually consistent.

## 12. Embedding Model Lock-In

- **Gotcha**: We benchmarked BGE-M3 vs MiniLM (Phase 14). BGE-M3 won (r@10=0.926 vs 0.923).
- **Risk**: Switching models requires re-embedding ALL entities (drop + recreate Qdrant collection). GTE-Qwen2 (1.5B) has known download issues via HuggingFace xet CDN.
- **Fix**: Stick with BGE-M3 unless recall drops below 0.9. Run `scripts/embedding_eval.py` to re-benchmark.

## 13. GapReport Entities

- **Gotcha**: The Librarian stores `GapReport` entities in FalkorDB during each cycle.
- **Risk**: Over time, stale GapReports accumulate. They have `detected_at` timestamps but no automatic cleanup.
- **Fix**: Use `prune_stale(days=30)` or manually archive old GapReports.
