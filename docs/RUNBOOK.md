# Runbook — Exocortex Operations Playbook

Ten incident recipes for common operational scenarios.

---

## 1. Qdrant Down / Unreachable

**Symptoms:** Search returns `[]`, `system_diagnostics()` shows `vector.status: error`.

```bash
# Check container
docker ps | grep qdrant
docker logs claude-memory-mcp-qdrant-1 --tail 50

# Restart
docker compose restart qdrant

# Verify
curl http://localhost:6333/collections/memory_embeddings
```

**Root cause:** OOM, disk full, or container eviction.

---

## 2. FalkorDB OOM / Eviction

**Symptoms:** Entity creation fails, `graph_health()` returns error.

```bash
# Check maxmemory
docker exec claude-memory-mcp-graphdb-1 redis-cli CONFIG GET maxmemory

# Should be 1073741824 (1GB). If 0, fix:
docker exec claude-memory-mcp-graphdb-1 redis-cli CONFIG SET maxmemory 1073741824
docker exec claude-memory-mcp-graphdb-1 redis-cli CONFIG SET maxmemory-policy noeviction
```

**Prevention:** `REDIS_ARGS` in `docker-compose.yml` enforces this at startup.

---

## 3. Split-Brain Drift (Graph ≠ Vector)

**Symptoms:** `system_diagnostics()` shows `split_brain.status: drift`.

```bash
# Identify drift
python -c "
import asyncio
from src.claude_memory.tools import MemoryService
from src.claude_memory.embedding import EmbeddingService
s = MemoryService(EmbeddingService())
print(asyncio.run(s.system_diagnostics()))
"

# Fix: re-embed all entities
python scripts/reembed_all.py

# Fix: purge orphan vectors
python scripts/purge_ghost_vectors.py
```

---

## 4. Missing Temporal Fields

**Symptoms:** `validate_brain.py` warns about missing `created_at` / `occurred_at`.

```bash
# Backfill
python scripts/backfill_temporal.py

# Verify
python scripts/validate_brain.py
```

---

## 5. Ghost Graphs in FalkorDB

**Symptoms:** `validate_brain.py` warns about unexpected graphs.

```bash
# List graphs
docker exec claude-memory-mcp-graphdb-1 redis-cli GRAPH.LIST

# Delete ghost graphs (replace GHOST_NAME)
docker exec claude-memory-mcp-graphdb-1 redis-cli GRAPH.DELETE GHOST_NAME
```

---

## 6. Observation Embeddings Missing

**Symptoms:** Deep search returns observations but they're not in vector results.

```bash
# Backfill observation embeddings
python scripts/embed_observations.py --dry-run  # preview
python scripts/embed_observations.py             # execute

# Verify count
python scripts/validate_brain.py
```

---

## 7. Backup & Restore

**Symptoms:** Need to snapshot or roll back the brain.

```bash
# Backup (creates timestamped folder in backups/)
python scripts/backup_restore.py save my-backup-name

# Restore
python scripts/backup_restore.py load my-backup-name --force

# Verify
docker exec claude-memory-mcp-graphdb-1 redis-cli --csv \
  GRAPH.QUERY claude_memory "MATCH (n) RETURN count(n)"
```

---

## 8. Unit Tests Failing After Code Change

**Symptoms:** `pytest` failures after modifying source code.

```bash
# Quick check (fail-fast)
python -m pytest tests/unit/ -x -q

# Full suite with coverage
tox -e pulse

# If pre-commit hooks also fail
git stash
tox -e pulse
git stash pop
```

---

## 9. Pre-Commit Hooks Blocking Commit

**Symptoms:** `git commit` rejected by ruff, codespell, or detect-secrets.

```bash
# Run hooks manually to see issues
pre-commit run --all-files

# Auto-fix ruff issues
ruff check --fix .
ruff format .

# Codespell false positives: add to pyproject.toml [tool.codespell] ignore-words-list
```

---

## 10. E2E Test Environment Setup

**Symptoms:** `e2e_functional.py` fails because backends are down.

```bash
# Start all backends
docker compose up -d

# Wait for health
sleep 5
curl http://localhost:6333/healthz        # Qdrant
docker exec claude-memory-mcp-graphdb-1 redis-cli PING  # FalkorDB
curl http://localhost:8001/health          # Embedder

# Run E2E (single phase for debugging)
python tests/e2e_functional.py --phase 5 --verbose

# Run full suite
python tests/e2e_functional.py --strict
```
