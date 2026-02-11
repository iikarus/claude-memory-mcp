# Structural Analysis Gate — 2026-02-11

> **Context**: Pre-Build Analysis for Audit Remediation Cycle 1
> **Commit**: Pre-fix state

## A. Flow Analysis

Tracing entry points to terminal operations (LOUD = error reaches caller, SILENT = error swallowed).

| Entry Point              | Path                                                                          | Terminal Op       | Failure Mode                                         |
| ------------------------ | ----------------------------------------------------------------------------- | ----------------- | ---------------------------------------------------- |
| `create_entity` (graph)  | `server` → `tools.MemoryService` → `crud.create_entity` → `repo.create_node`  | FalkorDB (Redis)  | **LOUD** (ConnectionError propagates)                |
| `create_entity` (vector) | `server` → `tools.MemoryService` → `crud.create_entity` → `vector.upsert`     | Qdrant            | **SILENT** (Swallowed + Warning)                     |
| `update_entity` (graph)  | `server` → `tools.MemoryService` → `crud.update_entity` → `repo.update_node`  | FalkorDB          | **LOUD**                                             |
| `update_entity` (vector) | `server` → `tools.MemoryService` → `crud.update_entity` → `vector.upsert`     | Qdrant            | **SILENT** (Swallowed + Warning)                     |
| `delete_entity` (graph)  | `server` → `tools.MemoryService` → `crud.delete_entity` → `repo.delete_node`  | FalkorDB          | **LOUD**                                             |
| `delete_entity` (vector) | `server` → `tools.MemoryService` → `crud.delete_entity` → `vector.delete`     | Qdrant            | **SILENT** (Swallowed + Warning)                     |
| `search_memory`          | `server` → `tools.MemoryService` → `search.search` → `vector.search`          | Qdrant            | **LOUD** (Retry exhausted → ConnectionError)         |
| `run_librarian_cycle`    | `tools_extra` → `LibrarianAgent.run_cycle` → `consolidate` / `prune`          | FalkorDB / Qdrant | **SILENT** (All exceptions swallowed to report dict) |
| `graph_health`           | `server` → `tools.MemoryService` → `analysis.get_graph_health` → `clustering` | Local CPU         | **SILENT** (Clustering error → community_count=0)    |
| `_fire_salience_update`  | `tools.MemoryService` → `Background Task` → `crud._fire_salience_update`      | FalkorDB          | **SILENT** (Logged warning, update dropped)          |
| `lock_manager.acquire`   | `lock_manager` → `redis`                                                      | Redis             | **LOUD** (ConnectionError → Fallback to File)        |

## B. Dependency Graph

| Module                  | Imports From (Internal)                                                                                                       | Imported By (Internal)                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `server.py`             | `tools`, `tools_extra`, `logging_config`                                                                                      | None (Entry Point)                             |
| `tools.py`              | `crud`, `search`, `temporal`, `analysis`, `interfaces`, `repository`, `vector_store`, `embedding`, `ontology`, `lock_manager` | `server.py`                                    |
| `tools_extra.py`        | `interfaces`, `search_advanced`, `librarian`                                                                                  | `server.py`                                    |
| `crud.py`               | `interfaces`, `schema`                                                                                                        | `tools.py`                                     |
| `search.py`             | `interfaces`, `schema`, `search_advanced`                                                                                     | `tools.py`                                     |
| `temporal.py`           | `interfaces`                                                                                                                  | `tools.py`                                     |
| `analysis.py`           | `interfaces`, `clustering`                                                                                                    | `tools.py`                                     |
| `search_advanced.py`    | `interfaces`, `activation`                                                                                                    | `search.py`, `tools_extra.py`                  |
| `repository_queries.py` | None                                                                                                                          | `repository.py`                                |
| `repository.py`         | `interfaces`, `repository_queries`, `retry`                                                                                   | `tools.py`                                     |
| `vector_store.py`       | `interfaces`, `retry`                                                                                                         | `tools.py`, `crud.py`, `search.py`             |
| `embedding.py`          | None                                                                                                                          | `tools.py`, `search.py`                        |
| `librarian.py`          | `interfaces`                                                                                                                  | `tools_extra.py`                               |
| `retry.py`              | `logging_config` (indirect via logging)                                                                                       | `repository.py`, `vector_store.py`             |
| `schema.py`             | None                                                                                                                          | `crud.py`, `search.py`, `interfaces.py`        |
| `interfaces.py`         | `schema`                                                                                                                      | All Mixins, `repository.py`, `vector_store.py` |

## C. Gate Verification

| Check                          | Status      | Value                                                            |
| ------------------------------ | ----------- | ---------------------------------------------------------------- |
| **Zero Circular Imports**      | ✅ PASS     | Verified in Audit 1                                              |
| **Zero Orphan Modules**        | ✅ PASS     | All modules connected to `server.py` tree                        |
| **Zero Modules > 300 Lines**   | ❌ **FAIL** | `repository.py`: **304 lines**                                   |
| **Silent Failures Documented** | ✅ PASS     | 5 documented above (Vector Ops, Librarian, Clustering, Salience) |

### Action Required

1. **Split `repository.py`** before proceeding with functionality fixes.
2. Accept the documented SILENT failures for now (will be fixed in remediation).
