# Structural Analysis — Pre-Remediation Baseline

**Generated**: 2026-02-13T12:42:00+03:00
**Commit**: Baseline snapshot before P0 remediation
**Purpose**: Directive §0 artifact — records module structure, dependency graph, error handling surfaces, and known gaps BEFORE any code changes.

---

## Module Inventory (28 source files)

| Module                    | Role                                        | Lines | Terminal Ops                                |
| ------------------------- | ------------------------------------------- | ----- | ------------------------------------------- |
| `server.py`               | MCP entrypoint, tool registration           | 296   | stdio transport                             |
| `tools.py`                | MemoryService god-class (mixin host)        | —     | FalkorDB, Qdrant, Embedder                  |
| `tools_extra.py`          | Extra MCP tool handlers                     | 165   | delegates to MemoryService                  |
| `crud.py`                 | Create/update/delete entity logic           | —     | FalkorDB (graph write)                      |
| `crud_maintenance.py`     | add_observation, archive, prune             | —     | FalkorDB (graph write)                      |
| `search.py`               | SearchMixin: semantic + structural search   | 257   | Qdrant (vector read), FalkorDB (graph read) |
| `search_advanced.py`      | SearchAdvancedMixin: associative + hologram | —     | Qdrant, FalkorDB, ActivationEngine          |
| `repository.py`           | MemoryRepository (graph CRUD)               | —     | FalkorDB                                    |
| `repository_queries.py`   | Query helpers (get_by_id, search)           | —     | FalkorDB                                    |
| `repository_traversal.py` | Graph traversal (BFS, shortest path)        | —     | FalkorDB                                    |
| `vector_store.py`         | QdrantVectorStore (vector CRUD)             | —     | Qdrant                                      |
| `embedding.py`            | EmbeddingService (encode text)              | —     | Embedding server HTTP                       |
| `embedding_server.py`     | FastAPI embedding server                    | —     | torch/sentence-transformers                 |
| `retry.py`                | Exponential backoff decorator               | 107   | —                                           |
| `temporal.py`             | Session/breakthrough temporal logic         | —     | FalkorDB                                    |
| `activation.py`           | Spreading activation engine                 | —     | in-memory                                   |
| `analysis.py`             | PageRank/Louvain analysis                   | —     | FalkorDB                                    |
| `clustering.py`           | Embedding clustering service                | —     | Qdrant, numpy                               |
| `context_manager.py`      | Context window management                   | —     | in-memory                                   |
| `graph_algorithms.py`     | Pure graph algorithm implementations        | —     | in-memory                                   |
| `interfaces.py`           | ABC interfaces (Embedder, VectorStore)      | —     | —                                           |
| `librarian.py`            | LibrarianAgent (auto-consolidate)           | —     | MemoryService, ClusteringService            |
| `lock_manager.py`         | Distributed lock                            | —     | Redis                                       |
| `logging_config.py`       | Logging setup                               | —     | —                                           |
| `ontology.py`             | Type registry + validation                  | —     | filesystem (ontology.json)                  |
| `router.py`               | QueryRouter (strategy dispatch)             | —     | —                                           |
| `schema.py`               | Pydantic models                             | —     | —                                           |
| `__init__.py`             | Package init                                | —     | —                                           |

---

## MCP Tool Entry Points (21 tools)

### server.py (13 tools — registered via `@mcp.tool()`)

| Tool                         | Entry Fn                       | Delegates To                           | Write?          | Error Handling          |
| ---------------------------- | ------------------------------ | -------------------------------------- | --------------- | ----------------------- |
| `create_entity`              | `create_entity()`              | `CrudMixin.create_entity`              | ✅ graph+vector | ⚠ PRECEDED_BY swallowed |
| `update_entity`              | `update_entity()`              | `CrudMixin.update_entity`              | ✅ graph        | —                       |
| `delete_entity`              | `delete_entity()`              | `CrudMaintenanceMixin.delete_entity`   | ✅ graph        | —                       |
| `create_relationship`        | `create_relationship()`        | `CrudMixin.create_relationship`        | ✅ graph        | —                       |
| `delete_relationship`        | `delete_relationship()`        | `CrudMixin.delete_relationship`        | ✅ graph        | —                       |
| `add_observation`            | `add_observation()`            | `CrudMaintenanceMixin.add_observation` | ✅ graph only   | ❌ No vector            |
| `start_session`              | `start_session()`              | `TemporalMixin.start_session`          | ✅ graph        | —                       |
| `end_session`                | `end_session()`                | `TemporalMixin.end_session`            | ✅ graph        | —                       |
| `record_breakthrough`        | `record_breakthrough()`        | `TemporalMixin.record_breakthrough`    | ✅ graph        | —                       |
| `search_memory`              | `search_memory()`              | `SearchMixin.search`                   | ❌ read         | ❌ No try/except        |
| `get_hologram`               | `get_hologram()`               | `SearchAdvancedMixin.get_hologram`     | ❌ read         | ❌ No try/except        |
| `analyze_graph`              | `analyze_graph()`              | `AnalysisMixin.analyze_graph`          | ❌ read         | —                       |
| `get_neighbors`              | `get_neighbors()`              | `SearchMixin.get_neighbors`            | ❌ read         | —                       |
| `traverse_path`              | `traverse_path()`              | `SearchMixin.traverse_path`            | ❌ read         | —                       |
| `find_cross_domain_patterns` | `find_cross_domain_patterns()` | `SearchMixin.find_cross_domain`        | ❌ read         | —                       |
| `get_evolution`              | `get_evolution()`              | `SearchMixin.get_evolution`            | ❌ read         | —                       |
| `point_in_time_query`        | `point_in_time_query()`        | `SearchMixin.point_in_time_query`      | ❌ read         | —                       |
| `archive_entity`             | `archive_entity()`             | `CrudMaintenanceMixin.archive_entity`  | ✅ graph        | —                       |
| `prune_stale`                | `prune_stale()`                | `CrudMaintenanceMixin.prune_stale`     | ✅ graph        | —                       |

### tools_extra.py (8 tools — registered via `configure()`)

| Tool                     | Entry Fn                   | Delegates To                             | Write?   | Error Handling   |
| ------------------------ | -------------------------- | ---------------------------------------- | -------- | ---------------- |
| `search_associative`     | `search_associative()`     | `SearchAdvancedMixin.search_associative` | ❌ read  | ❌ No try/except |
| `run_librarian_cycle`    | `run_librarian_cycle()`    | `LibrarianAgent.run_cycle`               | ✅ graph | —                |
| `create_memory_type`     | `create_memory_type()`     | `OntologyMixin.create_memory_type`       | ✅ file  | —                |
| `query_timeline`         | `query_timeline()`         | `TemporalMixin.query_timeline`           | ❌ read  | —                |
| `get_temporal_neighbors` | `get_temporal_neighbors()` | `TemporalMixin.get_temporal_neighbors`   | ❌ read  | —                |
| `get_bottles`            | `get_bottles()`            | `TemporalMixin.get_bottles`              | ❌ read  | —                |
| `graph_health`           | `graph_health()`           | `AnalysisMixin.get_graph_health`         | ❌ read  | —                |
| `find_knowledge_gaps`    | `find_knowledge_gaps()`    | `AnalysisMixin.detect_structural_gaps`   | ❌ read  | —                |

---

## Internal Dependency Graph

```
server.py
├── tools.py (MemoryService)
│   ├── crud.py (CrudMixin) → repository.py → FalkorDB
│   │                        → vector_store.py → Qdrant
│   │                        → embedding.py → Embedding HTTP
│   ├── crud_maintenance.py (CrudMaintenanceMixin) → repository.py
│   ├── search.py (SearchMixin) → repository.py, vector_store.py, embedding.py
│   │   └── search_advanced.py (SearchAdvancedMixin) → activation.py
│   ├── temporal.py (TemporalMixin) → repository.py
│   ├── analysis.py (AnalysisMixin) → graph_algorithms.py, repository.py
│   └── context_manager.py
├── tools_extra.py → tools.py, librarian.py
├── librarian.py → clustering.py → vector_store.py
├── ontology.py → filesystem
├── retry.py (decorator used by: repository.py, repository_queries.py, repository_traversal.py, vector_store.py)
└── schema.py (data models used everywhere)
```

**Circular dependencies**: None detected.

---

## Error Handling Surface — Known Gaps (pre-remediation)

| #   | Location                                        | Gap                                            | P0 Fix?            |
| --- | ----------------------------------------------- | ---------------------------------------------- | ------------------ |
| 1   | `crud.py:92-97`                                 | `except Exception` swallows PRECEDED_BY errors | P0-1               |
| 2   | `search.py` (`search()`, line ~156-256)         | No try/except on search pipeline               | P0-3               |
| 3   | `search_advanced.py` (`search_associative()`)   | No try/except on search pipeline               | P0-3               |
| 4   | `retry.py:15-28`                                | Missing Qdrant transient exceptions            | P0-4               |
| 5   | `crud_maintenance.py:45-74` (`add_observation`) | No vector upsert for observation text          | Design gap (§12.2) |
| 6   | `repository.py:91,158`                          | Cypher label/relation_type injection           | Deferred to P2     |

---

## Data Store Topology

| Store            | Container                        | Current State                                                     |
| ---------------- | -------------------------------- | ----------------------------------------------------------------- |
| FalkorDB         | `claude-memory-mcp-graphdb-1`    | 700 nodes, 800 edges, maxmemory=0, 4 graphs (1 active + 3 ghosts) |
| Qdrant           | `claude-memory-mcp-qdrant-1`     | 190 vectors (1024-dim), HNSW inactive, ~40 ghost vectors          |
| Embedding Server | `claude-memory-mcp-embeddings-1` | CUDA active, 966MB RAM                                            |
| Dashboard        | `claude-memory-mcp-dashboard-1`  | FastAPI, 50MB RAM                                                 |

---

## Files to be Modified in P0 Remediation

| File                             | P0 Item | Change Type                      |
| -------------------------------- | ------- | -------------------------------- |
| `crud.py`                        | P0-1    | Error surfacing                  |
| `test_memory_service.py`         | P0-1    | Test update                      |
| `docker-compose.yml`             | P0-2    | Config (maxmemory + loadmodule)  |
| `search.py`                      | P0-3    | Error handling                   |
| `test_memory_service.py`         | P0-3    | New tests                        |
| `retry.py`                       | P0-4    | Exception list                   |
| `test_retry.py`                  | P0-4    | New tests                        |
| `pyproject.toml`                 | P0-5    | Dep removal + mypy cleanup       |
| `Dockerfile`                     | P0-5    | Dep removal                      |
| `scripts/reembed_all.py`         | P0-0    | Batch re-embed (existing script) |
| `scripts/purge_ghost_vectors.py` | P0-0    | New script                       |
| `scripts/backfill_temporal.py`   | P0-6    | Temporal chain repair            |
