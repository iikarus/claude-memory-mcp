# Code Inventory

A manifest of the project structure.

## Core Logic (`src/claude_memory/`)

| File | Purpose |
|Data Access| |
| `repository.py` | **Data Access Layer**. Handles FalkorDB connections, Cypher queries, Vector Search, and Graph Algorithms. |
| `schema.py` | **Data Models**. Pydantic definitions for all inputs and outputs. |
|Services| |
| `tools.py` | **Business Logic**. `MemoryService` class. Handles Entity Lifecycle, Validation, and high-level operations. |
| `embedding.py` | **ML Layer**. Encapsulates `SentenceTransformer` logic. Strictly isolated. |
| `clustering.py` | **ML Layer**. Encapsulates `scikit-learn` logic for DBSCAN clustering. |
| `librarian.py` | **Autonomous Agent**. Orchestrates maintenance loops (Fetch -> Cluster -> Consolidate). |
| `interfaces.py` | **Protocols**. Defines abstract base classes (e.g., `Embedder`) for decoupling. |
|Entry Point| |
| `server.py` | **MCP Server**. Wires services together and exposes functions as MCP Tools. |

## Dashboard (`src/dashboard/`)

| File     | Purpose                                                                          |
| -------- | -------------------------------------------------------------------------------- |
| `app.py` | **Streamlit App**. Connects to `MemoryService` to visualize the graph and stats. |

## Tests (`tests/`)

| File                            | Coverage                                                        |
| ------------------------------- | --------------------------------------------------------------- |
| `unit/test_entity_lifecycle.py` | CRUD operations.                                                |
| `unit/test_hologram.py`         | Retrieval logic (Search + Subgraph).                            |
| `unit/test_librarian.py`        | Autonomous interaction logic.                                   |
| `unit/test_clustering.py`       | DBSCAN wrapper logic.                                           |
| `unit/test_interfaces.py`       | Protocol compliance.                                            |
| `unit/test_embedding_filter.py` | **Safety Check**. Verifies embedding stripping ("The Bouncer"). |

## Configuration

| File                 | Purpose                                                        |
| -------------------- | -------------------------------------------------------------- |
| `pyproject.toml`     | Dependencies, Build System, Tool Config (Black, Isort, Mypy).  |
| `Dockerfile`         | Multi-stage build definition.                                  |
| `docker-compose.yml` | Orchestration for DB + Server + Dashboard.                     |
| `mcp_config.json`    | **Local Config**. Arguments for running with `claude mcp run`. |

## Operations & Scripts (`scripts/`)

| File                    | Purpose                                                                 |
| ----------------------- | ----------------------------------------------------------------------- |
| **Safety & Ops**        |                                                                         |
| `backup_restore.py`     | **Snapshot Tool**. "Git-style" Save/Load for full database state.       |
| `nuke_data.py`          | **Reset Tool**. Wipes FalkorDB and Qdrant completely.                   |
| `start.ps1`             | **Startup**. Helper to resume Docker containers without rebuilding.     |
| **Verification**        |                                                                         |
| `red_team.py`           | **Chaos Testing**. Fuzzing, Concurrency, and Cycle detection.           |
| `e2e_test.py`           | **Full Stack Test**. Verifies Graph+Vector connectivity on live Docker. |
| `verify_mcp_server.py`  | **Protocol Test**. Simulates an MCP Client (JSON-RPC) to verify tools.  |
| `debug_data_status.py`  | **Diagnostic**. Counts nodes in FalkorDB directly.                      |
| `debug_qdrant_count.py` | **Diagnostic**. Counts vectors in Qdrant directly.                      |
| **Legacy/Utils**        |                                                                         |
| `simulate_day.py`       | Simulation of user interaction (Mocked).                                |
| `download_model.py`     | Pre-downloads ML models during Docker build.                            |
| `generate_config.py`    | Utils for config generation.                                            |
| `final_check.py`        | **E2E Verification**. The "Golden Master" test for system health.       |
| `docker_cleanup.ps1`    | **Hygiene**. Aggressive disk cleanup for Docker artifacts.              |
