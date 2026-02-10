# Code Inventory

A manifest of the project structure. Last updated: February 10, 2026.

## Core Logic (`src/claude_memory/`)

| File                  | Purpose                                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Data Access**       |                                                                                                                 |
| `repository.py`       | **Data Access Layer**. FalkorDB connections, Cypher queries, Graph Algorithms, Temporal queries.                |
| `vector_store.py`     | **Vector Access Layer**. Qdrant client, collection management, similarity search, MMR. Re-raises init errors.   |
| `schema.py`           | **Data Models**. Pydantic definitions for all inputs and outputs (30+ models).                                  |
| **Services**          |                                                                                                                 |
| `tools.py`            | **Business Logic**. `MemoryService` class. Entity Lifecycle, Validation, Hybrid Search, Salience, Gaps.         |
| `embedding.py`        | **ML Layer**. Wraps embedding API calls (remote) or local `SentenceTransformer`. Isolated.                      |
| `embedding_server.py` | **Embedding Microservice**. Standalone HTTP server for GPU-accelerated embedding generation.                    |
| `clustering.py`       | **ML Layer**. `scikit-learn` DBSCAN clustering + structural gap detection (`detect_gaps`).                      |
| `activation.py`       | **ML Layer**. `ActivationEngine` — spreading activation through graph edges for associative retrieval.          |
| `librarian.py`        | **Autonomous Agent**. Orchestrates maintenance loops (Fetch → Cluster → Consolidate → Gap Detect).              |
| `router.py`           | **Query Routing**. `QueryRouter` — rule-based intent classification (semantic/associative/temporal/relational). |
| `context_manager.py`  | **Session Management**. Context tracking for active sessions.                                                   |
| `interfaces.py`       | **Protocols**. Abstract base classes (e.g., `Embedder`) for decoupling.                                         |
| `ontology.py`         | **Type System**. Runtime ontology management for custom memory types.                                           |
| **Infrastructure**    |                                                                                                                 |
| `server.py`           | **MCP Server**. Wires services together, exposes 25 functions as MCP Tools. **stdio transport only.**           |
| `lock_manager.py`     | **Concurrency**. Redis-based distributed locking with file-based fallback.                                      |
| `retry.py`            | **Resilience**. `@retry_on_transient` decorator for handling transient connection failures.                     |
| `logging_config.py`   | **Logging**. Structured logging configuration.                                                                  |

## Dashboard (`src/dashboard/`)

| File     | Purpose                                                                                         |
| -------- | ----------------------------------------------------------------------------------------------- |
| `app.py` | **Streamlit App**. Graph visualization, stats, diagnostics. Healthchecked on `/_stcore/health`. |

## Tests (`tests/`)

| File                              | Coverage                                                        |
| --------------------------------- | --------------------------------------------------------------- |
| `test_schema.py`                  | Pydantic model validation (top-level).                          |
| **Unit Tests**                    |                                                                 |
| `unit/test_entity_lifecycle.py`   | CRUD operations.                                                |
| `unit/test_hologram.py`           | Retrieval logic (Search + Subgraph).                            |
| `unit/test_librarian.py`          | Autonomous interaction logic + gap detection.                   |
| `unit/test_clustering.py`         | DBSCAN wrapper + structural gap detection.                      |
| `unit/test_interfaces.py`         | Protocol compliance.                                            |
| `unit/test_embedding_filter.py`   | **Safety Check**. Verifies embedding stripping ("The Bouncer"). |
| `unit/test_server.py`             | MCP tool wrappers + `main()` stdio transport.                   |
| `unit/test_vector_store.py`       | Qdrant client, collection init, search, MMR, error re-raise.    |
| `unit/test_validation.py`         | Pydantic model validation.                                      |
| `unit/test_tools_coverage.py`     | Comprehensive MemoryService method coverage.                    |
| `unit/test_embedding_coverage.py` | Embedding service edge cases.                                   |
| `unit/test_embedding_client.py`   | Embedding client integration.                                   |
| `unit/test_embedding_server.py`   | Embedding HTTP server.                                          |
| `unit/test_lock_manager.py`       | Lock acquisition, release, TTL expiry (Redis path).             |
| `unit/test_lock_fallback.py`      | Lock fallback (file-based path).                                |
| `unit/test_locking.py`            | Concurrent locking scenarios.                                   |
| `unit/test_retry.py`              | Retry decorator logic.                                          |
| `unit/test_ontology.py`           | Custom type registration.                                       |
| `unit/test_logging_config.py`     | Logging setup.                                                  |
| `unit/test_memory_service.py`     | MemoryService integration tests (search, salience, gaps).       |
| `unit/test_repository.py`         | FalkorDB repository layer.                                      |
| `unit/test_activation.py`         | Spreading activation engine (decay, inhibition, ranking).       |
| `unit/test_router.py`             | Query intent classification + routing.                          |
| `unit/test_temporal.py`           | Temporal query and neighbor retrieval.                          |
| `unit/test_backfill_temporal.py`  | Temporal migration script tests.                                |
| `unit/test_session.py`            | Session lifecycle (start, end, breakthroughs).                  |
| `unit/test_context.py`            | Context manager tests.                                          |
| `unit/test_search_associative.py` | Associative search with spreading activation.                   |
| `unit/test_graph_traversal.py`    | Path finding and cross-domain patterns.                         |
| `unit/test_full_workflow.py`      | Multi-step workflow scenarios.                                  |
| `unit/test_edge_cases.py`         | Edge case coverage.                                             |
| `unit/test_dynamic_validation.py` | Dynamic Pydantic model validation.                              |
| `unit/test_phase4.py`             | Phase 4 regression tests.                                       |
| `unit/test_dashboard.py`          | Dashboard rendering.                                            |
| `unit/test_dashboard_app.py`      | Dashboard app integration.                                      |
| `unit/test_backup_restore.py`     | Backup/restore script tests.                                    |

**Total: 386 tests across 35 files, 98% coverage.**

## Configuration

| File                      | Purpose                                                                   |
| ------------------------- | ------------------------------------------------------------------------- |
| `pyproject.toml`          | Dependencies, Build System, Tool Config (Ruff, Mypy, Pytest).             |
| `tox.ini`                 | **CI/CD Tiers**: pulse, gate, forge, hammer, polish (5 tiers).            |
| `Dockerfile`              | Multi-stage build definition.                                             |
| `docker-compose.yml`      | Orchestration for DB + Embedding + Dashboard (all ports localhost-bound). |
| `.dockerignore`           | Excludes caches/backups from build context (~50 MB vs 1.6 GB).            |
| `.pre-commit-config.yaml` | Pre-commit hooks config.                                                  |
| `mcp_config.json`         | **Local Config**. Arguments for `claude mcp run`.                         |

## Operations & Scripts (`scripts/`)

| File                      | Purpose                                                                          |
| ------------------------- | -------------------------------------------------------------------------------- |
| **Backup & Ops**          |                                                                                  |
| `backup_restore.py`       | **Snapshot Tool**. "Git-style" Save/Load for full database state.                |
| `scheduled_backup.py`     | **Automated Backup**. Daily backup → Google Drive + rolling 7-day retention.     |
| `nuke_data.py`            | **Reset Tool**. Wipes FalkorDB and Qdrant completely.                            |
| `reset_db.py`             | **Soft Reset**. Database reset without full nuke.                                |
| `seed.py`                 | **Seeding**. Populates DB with test data.                                        |
| `start.ps1`               | **Startup**. Helper to resume Docker containers without rebuilding.              |
| `docker_cleanup.ps1`      | **Hygiene**. Aggressive disk cleanup for Docker artifacts.                       |
| `clean_tox.py`            | **Hygiene**. Cleans tox environments.                                            |
| **Verification**          |                                                                                  |
| `red_team.py`             | **Chaos Testing**. Fuzzing, Concurrency, and Cycle detection.                    |
| `e2e_test.py`             | **Full Stack Test**. Verifies Graph+Vector connectivity on live Docker.          |
| `verify_mcp_server.py`    | **Protocol Test**. Simulates an MCP Client (JSON-RPC) to verify tools.           |
| `final_check.py`          | **E2E Verification**. The "Golden Master" test for system health.                |
| `verify.py`               | **Quick Verify**. Lightweight verification script.                               |
| `verify_phase4.py`        | **Phase 4 Verify**. Phase-specific regression check.                             |
| `verify_dedup.py`         | **Dedup Verify**. Checks for duplicate entities.                                 |
| `verify_native_search.py` | **Search Verify**. Tests native search functionality.                            |
| `verify_read.py`          | **Read Verify**. Tests read operations.                                          |
| `verify_receipt.py`       | **Receipt Verify**. Tests transaction receipts.                                  |
| `debug_data_status.py`    | **Diagnostic**. Counts nodes in FalkorDB directly.                               |
| `debug_qdrant_count.py`   | **Diagnostic**. Counts vectors in Qdrant directly.                               |
| `debug_pagerank.py`       | **Diagnostic**. Tests PageRank algorithm on graph.                               |
| `debug_tar.py`            | **Diagnostic**. Tests tar archive operations.                                    |
| **Evaluation**            |                                                                                  |
| `embedding_eval.py`       | **Benchmark**. 3-stage embedding model evaluation harness (export/bench/report). |
| **Migration**             |                                                                                  |
| `backfill_temporal.py`    | **Migration**. Backfills `occurred_at` and `PRECEDED_BY` edges.                  |
| `migrate_vectors.py`      | **Migration**. Migrates vectors between collections.                             |
| `heal_graph.py`           | **Repair**. Fixes graph inconsistencies.                                         |
| `recover_graph.py`        | **Repair**. Recovers graph from backup data.                                     |
| **Utils**                 |                                                                                  |
| `download_model.py`       | Pre-downloads ML models during Docker build.                                     |
| `generate_config.py`      | Utils for config generation.                                                     |
| `simulate_lazy_import.py` | Tests lazy import behavior.                                                      |
| `simulate_day.py`         | Simulates a day of operations.                                                   |
| `operations.py`           | Operational utilities.                                                           |
