# Code Inventory

> **Last Updated**: 2026-03-09 | **Source Modules**: 28 | **Test Files**: 33 | **MCP Tools**: 30 (19 decorator + 11 runtime) | **Scripts**: 42

A manifest of the project structure.

## Core Logic (`src/claude_memory/`)

| File | Purpose |
|------|---------|
| **Entry Points** | |
| `__init__.py` | Package init. |
| `server.py` | **MCP Server**. Wires services together, exposes 19 decorator-based MCP tools. |
| `tools.py` | **MemoryService**. Primary service class composing all mixins. |
| `tools_extra.py` | **Extra MCP Tools**. 11 runtime-registered tools (search variants, temporal, librarian, health, orphans). |
| **Service Mixins** | |
| `analysis.py` | **AnalysisMixin**. Graph health, diagnostics, reconnect, gap detection, orphan listing. |
| `crud.py` | **CrudMixin**. Entity/relationship CRUD operations. |
| `crud_maintenance.py` | **CrudMaintenanceMixin**. Archive, prune, consolidate, stale entity detection. |
| `search.py` | **SearchMixin**. Core search and hologram retrieval. |
| `search_advanced.py` | **SearchAdvancedMixin**. Associative search with spreading activation. |
| `temporal.py` | **TemporalMixin**. Timeline queries, temporal neighbors, temporal edge creation. |
| **Data Access** | |
| `repository.py` | **MemoryRepository**. FalkorDB connection, graph selection, base persistence. |
| `repository_queries.py` | **RepositoryQueryMixin**. Cypher queries for timeline, health, bottles, orphans, edges. |
| `repository_traversal.py` | **RepositoryTraversalMixin**. Graph traversal, path finding, subgraph extraction. |
| **ML & Intelligence** | |
| `embedding.py` | **ML Layer**. SentenceTransformer embedding logic, strictly isolated. |
| `embedding_server.py` | **Embedding Server**. FastAPI microservice for embedding generation. |
| `clustering.py` | **ML Layer**. DBSCAN clustering via scikit-learn. |
| `activation.py` | **Spreading Activation**. Energy propagation through knowledge graph for associative search. |
| `graph_algorithms.py` | **Graph Algorithms**. PageRank, Louvain community detection wrappers. |
| `librarian.py` | **Autonomous Agent**. Maintenance loops (Fetch -> Cluster -> Consolidate). |
| **Infrastructure** | |
| `context_manager.py` | **Session Management**. Context tracking and session lifecycle. |
| `lock_manager.py` | **Concurrency Control**. Redis-based project locking with file-system fallback. |
| `vector_store.py` | **Vector Persistence**. Async Qdrant client wrapper. |
| `retry.py` | **Resilience**. Retry decorator for transient FalkorDB failures. |
| `logging_config.py` | **Logging**. Structured logging configuration. |
| **Schema & Config** | |
| `schema.py` | **Data Models**. Pydantic definitions for all inputs and outputs. |
| `ontology.py` | **Ontology Manager**. Dynamic memory type registration and validation. |
| `interfaces.py` | **Protocols**. Abstract base classes (e.g., `Embedder`) for decoupling. |
| `router.py` | **Router**. Request routing and tool dispatch logic. |

## MCP Tools (30 Total)

### Decorator-Registered (19) — `server.py`

Core CRUD, search, session, and graph analysis tools.

### Runtime-Registered (11) — `tools_extra.py`

| Tool | Purpose |
|------|---------|
| `search_associative` | Spreading activation search through knowledge graph. |
| `run_librarian_cycle` | Triggers autonomous maintenance loop. |
| `create_memory_type` | Registers new memory types in ontology. |
| `query_timeline` | Query entities within a time window. |
| `get_temporal_neighbors` | Find temporally connected entities. |
| `get_bottles` | Query "Message in a Bottle" entities. |
| `graph_health` | Graph health metrics: nodes, edges, density, orphans, communities. |
| `find_knowledge_gaps` | Detect structural gaps between semantically similar clusters. |
| `reconnect` | Session reconnect briefing for returning agents. |
| `system_diagnostics` | Unified diagnostics: graph stats, vector stats, split-brain check. |
| `list_orphans` | **NEW**. List graph nodes with zero relationships for triage. |

## Dashboard (`src/dashboard/`)

| File | Purpose |
|------|---------|
| `app.py` | **Streamlit App**. Visualizes graph, stats, and diagnostics. |

## Tests (`tests/unit/`) — 32 Files

| File | Coverage |
|------|----------|
| `test_backup_restore.py` | Backup/restore operations. |
| `test_clustering.py` | DBSCAN wrapper logic. |
| `test_context.py` | Context manager and sessions. |
| `test_dashboard.py` | Dashboard rendering. |
| `test_dashboard_app.py` | Dashboard app integration. |
| `test_dynamic_validation.py` | Dynamic validation logic. |
| `test_embedding_client.py` | Embedding client calls. |
| `test_embedding_coverage.py` | Embedding edge cases. |
| `test_embedding_filter.py` | Embedding stripping ("The Bouncer"). |
| `test_embedding_server.py` | Embedding server endpoints. |
| `test_entity_lifecycle.py` | CRUD operations. |
| `test_full_workflow.py` | End-to-end workflow. |
| `test_graph_traversal.py` | Graph traversal and path finding. |
| `test_hologram.py` | Retrieval logic (Search + Subgraph). |
| `test_interfaces.py` | Protocol compliance. |
| `test_librarian.py` | Autonomous interaction logic. |
| `test_list_orphans.py` | **NEW**. Orphan listing (3-evil/1-sad/1-happy + scenario). |
| `test_lock_fallback.py` | Lock manager fallback. |
| `test_locking.py` | Redis-based locking. |
| `test_logging_config.py` | Logging configuration. |
| `test_ontology.py` | Ontology management. |
| `test_phase4.py` | Phase 4 features. |
| `test_remaining_coverage.py` | Coverage gap tests. |
| `test_repository.py` | Repository operations. |
| `test_retry.py` | Retry decorator logic. |
| `test_server.py` | Server initialization. |
| `test_server_health.py` | Server health endpoints. |
| `test_session.py` | Session lifecycle. |
| `test_temporal.py` | Temporal queries. |
| `test_tools_coverage.py` | MemoryService tool coverage. |
| `test_validation.py` | Input validation. |
| `test_vector_store.py` | Vector store operations. |

## Configuration

| File | Purpose |
|------|---------|
| `pyproject.toml` | Dependencies, Build System, Tool Config (Black, Ruff, Mypy). |
| `Dockerfile` | Multi-stage build definition. |
| `docker-compose.yml` | Orchestration for DB + Server + Dashboard + Embeddings. |
| `mcp_config.json` | Local config for `claude mcp run`. |
| `tox.ini` | Gold Stack test configuration. |
| `ontology.json` | Memory type definitions. |
