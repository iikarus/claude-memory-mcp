# Scripts

Operational scripts for running, monitoring, and maintaining the Claude Memory MCP server.

## User-Facing Scripts

| Script | Purpose |
|--------|---------|
| `run_mcp_server.ps1` | Start the MCP server (used by Claude Desktop config) |
| `start.ps1` | Start all services (Docker + server) |
| `cold_run.ps1` | Fresh start: clean state, start services, verify |
| `cold_test.ps1` | Cold start specifically for test environment |
| `healthcheck.ps1` | Monitor service health (FalkorDB, Qdrant, Embedding API) |
| `backup_restore.py` | Backup and restore the knowledge graph |
| `scheduled_backup.py` | Automated backup with rotation |
| `setup_scheduled_tasks.ps1` | Register backups as Windows scheduled tasks |
| `docker_cleanup.ps1` | Clean up Docker volumes, images, containers |
| `download_model.py` | Download the BGE-M3 embedding model |
| `operations.py` | Operational utilities (graph stats, maintenance) |
| `mcp_smoke_test.py` | Quick verification that MCP tools respond correctly |
| `e2e_test.py` | 26-phase end-to-end integration test |

## Internal Scripts (`internal/`)

Development, migration, and diagnostic scripts. Not intended for end users.
Includes verification scripts, data migration tools, embedding evaluation,
simulation utilities, and security testing (red team).
