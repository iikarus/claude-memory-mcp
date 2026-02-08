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
