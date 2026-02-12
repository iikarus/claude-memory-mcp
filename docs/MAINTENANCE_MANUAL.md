# Maintenance Manual

Guidelines for keeping the Exocortex healthy and performant. Last updated: February 12, 2026.

## 🧹 The Librarian Agent

The Librarian (`src/claude_memory/librarian.py`) is an autonomous agent that runs optimization cycles.

### Configuration

Tune `src/claude_memory/clustering.py` parameters if clustering is too aggressive or too loose:

- `eps` (default 0.5): Distance threshold. Lower = Stricter clusters.
- `min_samples` (default 3): Minimum nodes to form a cluster.

### Triggering

Currently triggered manually via `run_librarian_cycle`.
**Future**: Set up a CRON job or Task Scheduler entry to trigger nightly.

## 💾 Backup & Restore

### Automated Daily Backup (Active)

A Windows Task Scheduler task (`ExocortexBackup`) runs daily at 3:00 AM:

1. Creates a local snapshot in `backups/daily_YYYY_MM_DD/`
2. Syncs to **Google Drive** (`G:\My Drive\exocortex_backups\`)
3. Deletes both local and cloud backups older than 7 days

**Script**: `scripts/scheduled_backup.py`

**Manual commands**:

```powershell
# Run backup now
python scripts/scheduled_backup.py

# Preview what would happen
python scripts/scheduled_backup.py --dry-run

# Check scheduler status
schtasks /query /tn "ExocortexBackup"
```

### Manual Backup (On-Demand)

For named snapshots before risky operations:

```powershell
python scripts/backup_restore.py save --tag "before_migration"
```

Snapshots are saved in `backups/<tag>/` containing `falkor_data.tar.gz` + `qdrant_data.tar.gz`.

### Restore (Load)

To roll back to a previous state:

```powershell
python scripts/backup_restore.py load "before_migration"
```

> **Warning**: This requires restarting Docker containers (`docker compose down && docker compose up -d`) to pick up the restored volume data.

## ☢️ Reset (Nuke)

To completely wipe all data (Graph + Vectors) and start fresh:

```powershell
python scripts/nuke_data.py
```

_Use with caution. Create a backup first._

## 🗑️ Pruning

Stale memories (Deleted or Archived) can accumulate.
Run `prune_stale(days=60)` to permanently delete archived items older than 60 days.

## 🛡️ Reliability Testing

### Red Team Operations (Stress Test)

```powershell
python scripts/red_team.py
```

### End-to-End UAT

The exhaustive User Acceptance Test exercises all 18 functional areas against the live Docker stack:

```powershell
python tests/e2e_functional.py
```

52 checks covering: entity CRUD, relationships, observations, semantic search (standard + MMR), graph traversal, temporal queries, sessions & breakthroughs, graph health, W3 strict consistency, associative search, graph algorithms (PageRank), hologram retrieval, memory consolidation, ontology management, archive/prune lifecycle, knowledge gap detection, and cleanup.

### Legacy E2E

```powershell
python scripts/e2e_test.py
```

## 🩺 Troubleshooting

### "Lock Acquisition Failed"

The system uses Redis-based locking (or File-based fallback).

- **Cause**: High concurrency or a lingering lock from a crashed process.
- **Fix**: Locks expire automatically (TTL 5-10s). Wait and retry.

### "Qdrant Connection Failed"

- Ensure `qdrant` container is running (Port 6333).
- **Env Var**: `QDRANT_HOST` must be set to `qdrant` inside Docker. Defaults to `localhost` for local scripts.
- **Check**: Run `python tests/e2e_functional.py` to diagnose connectivity.

### "Build Takes 3 Hours"

- **Cause**: Missing `.dockerignore` — entire project context sent to Docker daemon.
- **Fix**: Ensure `.dockerignore` exists and excludes `.tox/`, `backups/`, `.mypy_cache/`, `.git/`.

### Container Healthcheck Failures

| Container  | Check                  | Common Issue                                          |
| ---------- | ---------------------- | ----------------------------------------------------- |
| graphdb    | `redis-cli ping`       | FalkorDB not started yet (increase `start_period`)    |
| qdrant     | `bash /dev/tcp`        | Don't use curl/wget — Qdrant image lacks them         |
| embeddings | `curl /health`         | Model download not complete (increase `start_period`) |
| dashboard  | `curl /_stcore/health` | Streamlit startup delay                               |

## 📅 Scheduled Tasks

Registered by `scripts/setup_scheduled_tasks.ps1` (idempotent, run as admin):

| Task                   | Schedule         | Action                |
| ---------------------- | ---------------- | --------------------- |
| `ExocortexBackup`      | Daily at 3:00 AM | `scheduled_backup.py` |
| `ExocortexHealthCheck` | Every 15 minutes | `healthcheck.ps1`     |

## 🔒 Strict Consistency (W3)

Qdrant write failures always raise exceptions. This prevents split-brain scenarios (data in FalkorDB but not Qdrant). There is no env var toggle — strict mode is permanently enabled.
