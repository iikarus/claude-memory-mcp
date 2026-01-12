# Maintenance Manual

Guidelines for keeping the Exocortex healthy and performant.

## 🧹 The Librarian Agent

The Librarian (`src/claude_memory/librarian.py`) is an autonomous agent that runs optimization cycles.

### Configuration

Tune `src/claude_memory/clustering.py` parameters if clustering is too aggressive or too loose:

- `eps` (default 0.5): Distance threshold. Lower = Strieter clusters.
- `min_samples` (default 3): Minimum nodes to form a cluster.

### Triggering

Currently triggered manually via `run_librarian_cycle`.
**Future**: Set up a CRON job to hit the tool endpoint nightly.

## 💾 Backup & Restore

Data is stored in the `falkordb` docker volume.

### Full Backup (Docker)

```bash
# Stop the container
docker-compose stop db

# Backup volume
docker run --rm --volumes-from claude-memory-mcp-db-1 -v $(pwd):/backup ubuntu tar cvf /backup/memory_backup.tar /data
```

### Scripted Backup (Logical)

Use `scripts/operations.py` (if fully implemented for V2) or `falkordb-cli` to dump the graph.

## 🗑️ Pruning

Stale memories (Deleted or Archived) can accumulate.
Run `prune_stale(days=60)` to permanently delete archived items older than 60 days.

## 🛡️ Reliability Testing

### Red Team Operations (Stress Test)

Run the Chaos Engineering script to verify system stability against Fuzzing, Concurrency, and Graph Cycles.

```bash
python scripts/red_team.py
```

### End-to-End (E2E) Test

Verify the full stack (Graph + Vector) connectivity on live infrastructure.

```bash
python scripts/e2e_test.py
```

## 🩺 Troubleshooting

### "Lock Acquisition Failed"

The system uses Redis-based locking (or File-based fallback).

- **Cause**: High concurrency or a lingering lock from a crashed process.
- **Fix**: Locks expire automatically (TTL 5-10s). Wait and retry. If persistent, check `scripts/debug_concurrency.py`.

### "Qdrant Connection Failed"

- Ensure `qdrant` container is running (Port 6333).
- **Env Var**: `QDRANT_HOST` defaults to `localhost` for local scripts, but `qdrant` for Docker services.
- **Check**: Run `python scripts/e2e_test.py` to diagnose connectivity.

### "Mypy Error" in Pre-commit

If you encounter `unused "type: ignore"`, it means the typing environment has improved or changed.
**Fix**: Remove the unused `# type: ignore` comment.
