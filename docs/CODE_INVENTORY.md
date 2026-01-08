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

| File                            | Coverage                             |
| ------------------------------- | ------------------------------------ |
| `unit/test_entity_lifecycle.py` | CRUD operations.                     |
| `unit/test_hologram.py`         | Retrieval logic (Search + Subgraph). |
| `unit/test_librarian.py`        | Autonomous interaction logic.        |
| `unit/test_clustering.py`       | DBSCAN wrapper logic.                |
| `unit/test_interfaces.py`       | Protocol compliance.                 |

## Configuration

| File                 | Purpose                                                       |
| -------------------- | ------------------------------------------------------------- |
| `pyproject.toml`     | Dependencies, Build System, Tool Config (Black, Isort, Mypy). |
| `Dockerfile`         | Multi-stage build definition.                                 |
| `docker-compose.yml` | Orchestration for DB + Server + Dashboard.                    |
