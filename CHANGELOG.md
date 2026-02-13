# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **E-1: Bottle Reader with Content** (`bd2df89`) — `include_content` parameter
  in `BottleQueryParams` and `get_bottles()` to hydrate bottles with observation
  content in a single call.
- **E-2: Deep Search** (`1f3a1e5`) — `deep: bool` parameter on `search()` that
  hydrates results with associated observations and relationships.
- **E-3: Observation Vectorization** (`9f31e12`) — Automatic embedding of
  observation content upon creation; vectors upserted to Qdrant.
- **E-4: Session Reconnect** (`0588888`) — `reconnect()` method returning a
  structured briefing (recent entities, graph health, time window) for returning
  agents.
- **E-5: System Diagnostics** (`028fa3f`) — Unified `system_diagnostics()` method
  with graph health, vector store count, and split-brain detection.
- **E-6: Procedural Memory** (`ec588ab`) — `Procedure` entity type added to the
  ontology with step-based structure.
- **E-7: E2E Script Enhancement** (`907b5dc`) — `argparse` CLI (`--phase`,
  `--skip-cleanup`, `--strict`, `--verbose`), 8 new E2E phases (19–26), and
  per-phase latency threshold warnings (5s).
- `scripts/validate_brain.py` — 9-check live brain health validator (split-brain,
  bottle chain, temporal completeness, obs vectors, maxmemory, ghost graphs,
  orphan vectors, indices, HNSW threshold).
- `scripts/purge_ghost_vectors.py` (`6167ae6`) — Utility to remove orphan Qdrant
  vectors with no matching graph entity.

### Fixed

- **P0-0** (`6167ae6`) — Re-embedded all 464 entities after vector store rebuild.
- **P0-1** (`eea3ed8`) — Surface `PRECEDED_BY` errors in `EntityCommitReceipt.warnings`.
- **P0-2** (`26d7870`) — Set FalkorDB `maxmemory 1GB` + `noeviction` via `REDIS_ARGS`.
- **P0-3** (`7b9276f`) — Wrap `search()` and `search_associative()` in error handling.
- **P0-4** (`370919b`) — Add Qdrant `UnexpectedResponse` + `RpcError` to
  `retry_on_transient`.
- **P0-5** (`3976b65`) — Remove phantom dependencies (`graphiti-core`, `neo4j`, `pandas`).
- **P0-6** (`b8c4d34`) — Ghost graph cleanup, temporal backfill, FalkorDB query fix.
- `traverse_path` shortestPath FalkorDB compatibility (`f33ab01`).
- `get_bottles` label query fix (`f33ab01`).
- Custom Louvain replaced with NetworkX + `log2` salience bug fix (`54dcaec`).
- `OntologyManager` CWD-relative path fix (`6c7e616`).
- Bare `except Exception` catches narrowed to specific types across 7 files.

### Changed

- E2E test suite expanded from 18 to 26 phases.
- Unit test suite: 460 tests, 0 failures.
- Pre-commit hooks: ruff, ruff-format, codespell, detect-secrets all passing.
