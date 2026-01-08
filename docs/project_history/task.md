# Project Kickoff

[x] Create new workspace directory <!-- id: 0 -->
[x] Review spec document and ask questions <!-- id: 1 -->
[x] Create Implementation Plan (Hybrid Strategy) <!-- id: 2 -->
[x] Set up Infrastructure (Docker + FalkorDB) <!-- id: 3 -->
[x] Maximum Mercenaries Deployed (Dev dependencies & Pre-commit) <!-- id: 4 -->
[x] Debug Graphiti Connection (Greenfield Seed/Base Labels) <!-- id: 7 -->
[x] Verify System (Semantic Search Active via Fallback) <!-- id: 8 -->

# Phase 2: Completing the Spec

## Entity & Relationship Management

[x] Implement `add_observation` tool <!-- id: 9 -->
[x] Implement `update_entity` tool <!-- id: 10 -->
[x] Implement `delete_entity` tool <!-- id: 11 -->
[x] Implement `delete_relationship` tool <!-- id: 12 -->
[x] Unit Tests: Entity Lifecycle <!-- id: 13 -->

## Session Management

[x] Implement `start_session` tool <!-- id: 14 -->
[x] Implement `end_session` tool <!-- id: 15 -->
[x] Unit Tests: Session Flow <!-- id: 16 -->

## Advanced Retrieval

[x] Implement `get_neighbors` / `traverse_path` <!-- id: 17 -->
[x] Implement `find_cross_domain_patterns` <!-- id: 18 -->
[x] Unit Tests: Graph Traversal <!-- id: 19 -->

## Temporal & Maintenance

[x] Implement `get_evolution` & `point_in_time_query` <!-- id: 20 -->
[x] Implement `archive_entity` & `prune_stale` <!-- id: 21 -->
[x] Unit Tests: Temporal Logic <!-- id: 22 -->

## Operations & Final Polish

[x] create `scripts/operations.py` (Backup/Restore) <!-- id: 23 -->
[x] Implement `health_check()` in `operations.py` <!-- id: 24 -->
[x] Same-Day Verification (21/21 Tests Passed and Decoupled) <!-- id: 25 -->

# Phase 3: Optimization & CI/CD

## Infrastructure & Pipelines

[x] Create `.github/workflows/ci.yml` <!-- id: 26 -->
[x] Verify CI/CD pipeline locally (simulated) <!-- id: 27 -->

## Vector Optimization

[x] Refactor `tools.py` for Native Vector Indexing <!-- id: 28 -->
[x] Verify Search Performance & Correctness <!-- id: 29 -->

# Phase 4: Cognitive Evolution

## GraphRAG (Context Expansion)

[x] Implement `analyze_graph` tool (PageRank/Community) <!-- id: 30 -->
[x] Verify algorithmic insights <!-- id: 31 -->

## Autonomous Memory Management

[x] Implement `get_stale_entities` tool (Inspection) <!-- id: 32 -->
[x] Refactor MemoryService to use Repository (Decoupling)
[x] Update Unit Tests for Decoupled Architecture
[x] Implement `consolidate_memories` tool (Merge/Summary) <!-- id: 33 -->

## Visual Explorer

[x] create `src/dashboard/app.py` (Streamlit) <!-- id: 34 -->
[x] Connect Dashboard to FalkorDB <!-- id: 35 -->

## Phase 7: Architecture Decoupling

[x] Create `src/claude_memory/embedding.py` (Isolate ML) <!-- id: 39 -->
[x] Refactor `MemoryService` to use `EmbeddingService` <!-- id: 40 -->
[x] Update Unit Tests to mock `EmbeddingService` <!-- id: 41 -->

## Phase 8: Abstractions & Interfaces

[x] Create `src/claude_memory/interfaces.py` (Embedder Protocol) <!-- id: 42 -->
[x] Refactor `MemoryService` to use `Embedder` Protocol <!-- id: 43 -->
[x] Make `EmbeddingService` import lazy in `MemoryService` <!-- id: 44 -->
[x] Verify Protocol Adherence with Tests <!-- id: 45 -->

## Phase 9: Fluidity (Docker & Async)

[x] Create `Dockerfile` (Service & Dashboard) <!-- id: 46 -->
[x] Create `docker-compose.yml` (Full Stack: DB, App, UI) <!-- id: 47 -->
[x] Verify Build & Run (Mercenary Check Passed) <!-- id: 48 -->

## Phase 10: Holographic Retrieval

[x] Implement `get_hologram` (Search + BFS) <!-- id: 49 -->
[x] Add Unit Tests for Hologram <!-- id: 50 -->
[x] Verify with Pre-commit (Mercenary Check Passed) <!-- id: 51 -->

## Phase 11: Architecture Cleanup & Simplification

- [x] Analyze codebase dependencies (`dependency_analysis.md`)
- [x] **Decouple**: Remove default `EmbeddingService` from `MemoryService` (Strict DI)
- [x] Update Interface Tests (`test_interfaces.py`)
- [x] **Mypy Zero Policy**: Fix all type errors (100% Passed)
- [x] Verify Pre-commit Compliance (Mercenary Check Passed)

## Phase 12: The Librarian (Autonomous Configuration)

- [x] Add `scikit-learn` dependency
- [x] Implement `ClusteringService` (DBSCAN)
- [x] Implement `LibrarianAgent` (Loop)
- [x] Integrate with `server.py`
- [x] Verify with new Unit Tests (`test_clustering.py`, `test_librarian.py`)
- [x] **Mercenary Check**: Pre-commit Passed
