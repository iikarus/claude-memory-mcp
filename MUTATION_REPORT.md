# Dragon Brain Mutation Report
**Date:** 2026-02-24
**Runner:** Jules
**Repository:** claude-memory-mcp (master)
**Tool:** mutatest

## Summary

| Module | Mutants | Killed | Survived | Timeout | Error | Kill Rate |
|--------|---------|--------|----------|---------|-------|-----------|
| analysis.py | 8 | 0 | 0 | 8 | 0 | 0.0% |
| search.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| crud.py | 3 | 0 | 0 | 3 | 0 | 0.0% |
| vector_store.py | 8 | 0 | 0 | 8 | 0 | 0.0% |
| repository.py | 4 | 0 | 0 | 0 | 4 | 0.0% |
| repository_queries.py | 4 | 0 | 0 | 2 | 2 | 0.0% |
| repository_traversal.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| clustering.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| activation.py | 3 | 0 | 0 | 3 | 0 | 0.0% |
| search_advanced.py | 4 | 0 | 0 | 0 | 4 | 0.0% |
| router.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| schema.py | 4 | 0 | 0 | 0 | 4 | 0.0% |
| temporal.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| lock_manager.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| retry.py | ? | ? | ? | ? | ? | ? |
| embedding.py | 4 | 0 | 0 | 2 | 2 | 0.0% |
| ontology.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| librarian.py | 5 | 0 | 0 | 5 | 0 | 0.0% |
| crud_maintenance.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| context_manager.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| logging_config.py | 4 | 0 | 0 | 2 | 2 | 0.0% |
| server.py | 3 | 0 | 0 | 3 | 0 | 0.0% |
| tools.py | 4 | 0 | 0 | 2 | 2 | 0.0% |
| tools_extra.py | 4 | 0 | 0 | 0 | 4 | 0.0% |
| graph_algorithms.py | 7 | 0 | 0 | 7 | 0 | 0.0% |
| interfaces.py | 4 | 0 | 0 | 4 | 0 | 0.0% |
| **TOTAL** | **109** | **0** | **0** | **85** | **24** | **0.0%** |

## Per-Survivor Details

No survivors found (most mutations timed out or errored).

## Modules Below 75% Kill Rate (P0)

- analysis.py: 0.0%
- search.py: 0.0%
- crud.py: 0.0%
- vector_store.py: 0.0%
- repository.py: 0.0%
- repository_queries.py: 0.0%
- repository_traversal.py: 0.0%
- clustering.py: 0.0%
- activation.py: 0.0%
- search_advanced.py: 0.0%
- router.py: 0.0%
- schema.py: 0.0%
- temporal.py: 0.0%
- lock_manager.py: 0.0%
- embedding.py: 0.0%
- ontology.py: 0.0%
- librarian.py: 0.0%
- crud_maintenance.py: 0.0%
- context_manager.py: 0.0%
- logging_config.py: 0.0%
- server.py: 0.0%
- tools.py: 0.0%
- tools_extra.py: 0.0%
- graph_algorithms.py: 0.0%
- interfaces.py: 0.0%

## Modules Completed vs Pending

| Status | Modules |
|--------|---------|
| Completed | analysis.py, search.py, crud.py, vector_store.py, repository.py, repository_queries.py, repository_traversal.py, clustering.py, activation.py, search_advanced.py, router.py, schema.py, temporal.py, lock_manager.py, embedding.py, ontology.py, librarian.py, crud_maintenance.py, context_manager.py, logging_config.py, server.py, tools.py, tools_extra.py, graph_algorithms.py, interfaces.py |
| Timeout/Pending | retry.py (Missing) |

## Bugs Discovered (DO NOT FIX — document only)

CRITICAL: Mutation testing inconclusive due to environmental/performance issues.
- **Total Timeouts:** 85
- **Total Errors:** 24
- The test suite takes ~140s to run (clean trial), exceeding the mutation timeout of 30s.
- Some tests rely on Redis, which is causing ConnectionRefusedError unless skipped.
- `retry.py` failed to complete due to overall timeout.
