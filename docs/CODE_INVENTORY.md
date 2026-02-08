# Code Inventory

A manifest of the project structure. Last updated: February 2026.

## Core Logic (`src/claude_memory/`)

| File                  | Purpose                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------- |
| **Data Access**       |                                                                                                          |
| `repository.py`       | **Data Access Layer**. FalkorDB connections, Cypher queries, Graph Algorithms.                           |
| `vector_store.py`     | **Vector Access Layer**. Qdrant client, collection management, similarity search. Re-raises init errors. |
| `schema.py`           | **Data Models**. Pydantic definitions for all inputs and outputs.                                        |
| **Services**          |                                                                                                          |
| `tools.py`            | **Business Logic**. `MemoryService` class. Entity Lifecycle, Validation, Hybrid Search.                  |
| `embedding.py`        | **ML Layer**. Wraps embedding API calls (remote) or local `SentenceTransformer`. Isolated.               |
| `embedding_server.py` | **Embedding Microservice**. Standalone HTTP server for GPU-accelerated embedding generation.             |
| `clustering.py`       | **ML Layer**. `scikit-learn` DBSCAN clustering for concept discovery.                                    |
| `librarian.py`        | **Autonomous Agent**. Orchestrates maintenance loops (Fetch → Cluster → Consolidate).                    |
| `interfaces.py`       | **Protocols**. Abstract base classes (e.g., `Embedder`) for decoupling.                                  |
| **Infrastructure**    |                                                                                                          |
| `server.py`           | **MCP Server**. Wires services together, exposes functions as MCP Tools. **stdio transport only.**       |
| `lock_manager.py`     | **Concurrency**. Redis-based distributed locking with file-based fallback.                               |
| `retry.py`            | **Resilience**. `@retry_on_transient` decorator for handling transient connection failures.              |
| `ontology.py`         | **Type System**. Runtime ontology management for custom memory types.                                    |
| `logging_config.py`   | **Logging**. Structured logging configuration.                                                           |

## Dashboard (`src/dashboard/`)

| File     | Purpose                                                                                         |
| -------- | ----------------------------------------------------------------------------------------------- |
| `app.py` | **Streamlit App**. Graph visualization, stats, diagnostics. Healthchecked on `/_stcore/health`. |

## Tests (`tests/`)

| File                              | Coverage                                                        |
| --------------------------------- | --------------------------------------------------------------- |
| `unit/test_entity_lifecycle.py`   | CRUD operations.                                                |
| `unit/test_hologram.py`           | Retrieval logic (Search + Subgraph).                            |
| `unit/test_librarian.py`          | Autonomous interaction logic.                                   |
| `unit/test_clustering.py`         | DBSCAN wrapper logic.                                           |
| `unit/test_interfaces.py`         | Protocol compliance.                                            |
| `unit/test_embedding_filter.py`   | **Safety Check**. Verifies embedding stripping ("The Bouncer"). |
| `unit/test_server.py`             | MCP tool wrappers + `main()` stdio transport.                   |
| `unit/test_vector_store.py`       | Qdrant client, collection init, search, error re-raise.         |
| `unit/test_validation.py`         | Pydantic model validation.                                      |
| `unit/test_tools_coverage.py`     | Comprehensive MemoryService method coverage.                    |
| `unit/test_embedding_coverage.py` | Embedding service edge cases.                                   |
| `unit/test_lock_manager.py`       | Lock acquisition, release, TTL expiry.                          |
| `unit/test_retry.py`              | Retry decorator logic.                                          |
| `unit/test_ontology.py`           | Custom type registration.                                       |
| `unit/test_logging_config.py`     | Logging setup.                                                  |

**Total: 255 tests, 100% coverage.**

## Configuration

| File                      | Purpose                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| `pyproject.toml`          | Dependencies, Build System, Tool Config (Ruff, Mypy, Pytest).                            |
| `tox.ini`                 | **CI/CD Tiers**: pulse (lint+test), gate (security), hammer (mutation), polish (format). |
| `Dockerfile`              | Multi-stage build definition.                                                            |
| `docker-compose.yml`      | Orchestration for DB + Embedding + Dashboard (all ports localhost-bound).                |
| `.dockerignore`           | Excludes caches/backups from build context (~50 MB vs 1.6 GB).                           |
| `.pre-commit-config.yaml` | Pre-commit hooks config.                                                                 |
| `mcp_config.json`         | **Local Config**. Arguments for `claude mcp run`.                                        |

## Operations & Scripts (`scripts/`)

| File                    | Purpose                                                                      |
| ----------------------- | ---------------------------------------------------------------------------- |
| **Backup & Ops**        |                                                                              |
| `backup_restore.py`     | **Snapshot Tool**. "Git-style" Save/Load for full database state.            |
| `scheduled_backup.py`   | **Automated Backup**. Daily backup → Google Drive + rolling 7-day retention. |
| `nuke_data.py`          | **Reset Tool**. Wipes FalkorDB and Qdrant completely.                        |
| `start.ps1`             | **Startup**. Helper to resume Docker containers without rebuilding.          |
| `docker_cleanup.ps1`    | **Hygiene**. Aggressive disk cleanup for Docker artifacts.                   |
| **Verification**        |                                                                              |
| `red_team.py`           | **Chaos Testing**. Fuzzing, Concurrency, and Cycle detection.                |
| `e2e_test.py`           | **Full Stack Test**. Verifies Graph+Vector connectivity on live Docker.      |
| `verify_mcp_server.py`  | **Protocol Test**. Simulates an MCP Client (JSON-RPC) to verify tools.       |
| `final_check.py`        | **E2E Verification**. The "Golden Master" test for system health.            |
| `debug_data_status.py`  | **Diagnostic**. Counts nodes in FalkorDB directly.                           |
| `debug_qdrant_count.py` | **Diagnostic**. Counts vectors in Qdrant directly.                           |
| **Utils**               |                                                                              |
| `download_model.py`     | Pre-downloads ML models during Docker build.                                 |
| `generate_config.py`    | Utils for config generation.                                                 |
