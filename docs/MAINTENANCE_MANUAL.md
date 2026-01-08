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

## 🩺 Troubleshooting

### "Mypy Error" in Pre-commit

If you encounter `unused "type: ignore"`, it means the typing environment has improved or changed.
**Fix**: Remove the unused `# type: ignore` comment.

### "Connection Refused"

Ensure FalkorDB is running on Port 6379.
Host is configured via `FALKORDB_HOST` env var (default: `localhost`).
