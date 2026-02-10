# REHYDRATION DOCUMENT: The Dragon Brain Protocol

> **"If this system is a dragon, here is how to wake it up without getting burned."**

## 1. Mission Overview

This project, **Claude Memory MCP**, is a persistent "External Brain" for LLMs (specifically Claude and Gemini). It solves the context window limit by storing knowledge in a **Hybrid Architecture**:

- **FalkorDB (Graph Database)**: Stores semantic relationships (`Entity` → `PART_OF` → `Concept`). Port `6379`.
- **Qdrant (Vector Database)**: Stores high-dimensional embeddings for fuzzy search. Port `6333`.
- **Embedding Microservice**: A dedicated container running `BAAI/bge-m3` (1024d) for GPU-accelerated embedding generation. Port `8001`.
- **MCP Server (Python)**: The API layer using **stdio** transport to connect the LLM to these databases.
- **Dashboard (Streamlit)**: Visual graph explorer and diagnostics. Port `8501`.

## 2. Quick Start (Wake the Dragon)

If you are landing here fresh (new machine, new agent):

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Git

### Startup Sequence

1.  **Boot Infrastructure**:

    ```powershell
    docker compose up -d
    ```

    _Wait for all healthchecks to pass (~30 seconds)._

2.  **Verify Health**:

    ```powershell
    docker compose ps
    ```

    All 4 containers (graphdb, qdrant, embeddings, dashboard) should show `healthy`.

3.  **Install Dependencies** (for local dev/testing):

    ```powershell
    pip install -e .
    ```

4.  **Run End-to-End Verification**:

    ```powershell
    python scripts/final_check.py
    ```

    _If this passes, the system is 100% operational._

5.  **Connect Client**:
    Add the configuration from `mcp_config.json` to your MCP Client (Claude Desktop or VS Code).

## 3. The Architecture (Mental Map)

Do not treat this as a simple CRUD app. It is a **Synchronized Dual-Store**.

```mermaid
graph TD
    User[LLM / User] -->|stdio| Server[MCP Server]
    Server -->|HTTP| Embedder[Embedding Service :8001]
    Server -->|Cypher| Graph[FalkorDB :6379]
    Server -->|gRPC| Vector[Qdrant :6333]

    subgraph "The Dual-Store Contract"
    Graph -- Source of Truth --> Structure
    Vector -- Source of Truth --> Search
    end

    Dashboard[Streamlit :8501] -->|imports library| Server
```

### Critical Rules

1.  **Never Write to One DB Only**: Use `MemoryService.create_entity`. It writes to BOTH.
2.  **Embeddings Live in Qdrant Only**: Embeddings are NOT stored on FalkorDB graph nodes.
    - The `get_all_nodes` query has NO `WHERE n.embedding IS NOT NULL` filter.
    - **CRITICAL**: The API strips embeddings from responses to prevent flooding the LLM context window.

## 4. Operational Drills (Maintenance)

### Backup (Automated)

Backups run daily at 3:00 AM via Windows Task Scheduler → Google Drive.

```powershell
# Manual backup
python scripts/backup_restore.py save --tag my_backup

# Check automated backup status
schtasks /query /tn "ExocortexDailyBackup"
```

- **Local**: `backups/daily_YYYY_MM_DD/` (rolling 7-day)
- **Cloud**: `G:\My Drive\exocortex_backups\daily_YYYY_MM_DD/` (rolling 7-day)

### Restore

```powershell
python scripts/backup_restore.py load "my_backup"
# Then restart containers:
docker compose down && docker compose up -d
```

### Emergency Data Wipe (Nuke)

```powershell
python scripts/nuke_data.py --force
```

## 5. The Quality Stack (CI/CD)

**Do not commit code without running these.**

Run `tox -e pulse` — this executes all checks in one command:

1.  **Ruff**: Linting + import sorting.
2.  **Ruff Format**: Code formatting.
3.  **Mypy**: Static type checking (18 source files, strict mode).
4.  **Pytest**: 386 unit tests, 98% coverage (≥30% threshold).

Full 5-tier Gold Stack: `tox -e pulse` (lint+test), `tox -e gate` (security), `tox -e forge` (focused tests), `tox -e hammer` (mutation), `tox -e polish` (final format).

## 6. Known "Gotchas" for Future Agents

See `docs/GOTCHAS.md` for the full list. Top 3:

1.  **QDRANT_HOST**: Must be `qdrant` inside Docker, `localhost` locally. If missing, vector search silently fails.
2.  **No curl in Qdrant image**: Healthcheck uses `bash /dev/tcp`, not curl.
3.  **cp1252 Encoding**: Headless Windows scripts need `PYTHONUTF8=1` for unicode output.

## 7. Directives for the Next Agent

Hello, future intelligence. 👋
If you are reading this to fix a bug or add a feature:

1.  **Read `tests/unit/test_embedding_filter.py`**: It demonstrates the "Bouncer" logic.
2.  **Do not break the Sync**: If you add a field to FalkorDB, ask "Does Qdrant need this for filtering?"
3.  **Trust `e2e_test.py`**: It is your ground truth. If it fails, the system is broken.
4.  **Run `tox -e pulse` before committing**: 386 tests must pass.
5.  **Never add `WHERE n.embedding IS NOT NULL`**: Embeddings are in Qdrant, not on graph nodes.
6.  **Read `docs/UPGRADE_LOG.md`**: Understand what V2 added before making changes.
7.  **Read `docs/GOTCHAS.md`**: Known traps that will burn you if ignored.

_Signed,_
_Project Antigravity (Feb 2026)_
