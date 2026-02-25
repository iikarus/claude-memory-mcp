# Dragon Brain Mutation Report
**Date:** 2026-02-25
**Runner:** Jules
**Repository:** claude-memory-mcp (master)
**Tool:** mutatest

## Summary

| Module | Mutants | Killed | Survived | Timeout | Error | Kill Rate |
|--------|---------|--------|----------|---------|-------|-----------|
| analysis.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| search.py | ? | ? | ? | ? | ? | ? |
| crud.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| vector_store.py | 3 | 0 | 1 | 0 | 2 | 0.0% |
| repository.py | 7 | 0 | 7 | 0 | 0 | 0.0% |
| repository_queries.py | 8 | 8 | 0 | 0 | 0 | 100.0% |
| repository_traversal.py | 4 | 0 | 2 | 0 | 2 | 0.0% |
| clustering.py | 6 | 4 | 2 | 0 | 0 | 66.7% |
| activation.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| search_advanced.py | ? | ? | ? | ? | ? | ? |
| router.py | 3 | 0 | 3 | 0 | 0 | 0.0% |
| schema.py | 4 | 0 | 2 | 0 | 2 | 0.0% |
| temporal.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| lock_manager.py | 4 | 2 | 0 | 0 | 2 | 50.0% |
| retry.py | ? | ? | ? | ? | ? | ? |
| embedding.py | 3 | 0 | 3 | 0 | 0 | 0.0% |
| ontology.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| librarian.py | 9 | 3 | 6 | 0 | 0 | 33.3% |
| crud_maintenance.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| context_manager.py | 5 | 5 | 0 | 0 | 0 | 100.0% |
| logging_config.py | 4 | 4 | 0 | 0 | 0 | 100.0% |
| server.py | 4 | 3 | 1 | 0 | 0 | 75.0% |
| tools.py | 4 | 0 | 2 | 0 | 2 | 0.0% |
| tools_extra.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| graph_algorithms.py | 7 | 0 | 7 | 0 | 0 | 0.0% |
| interfaces.py | 4 | 0 | 4 | 0 | 0 | 0.0% |
| **TOTAL** | **107** | **29** | **68** | **0** | **10** | **27.1%** |

## Per-Survivor Details

### [analysis.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 44 | If_Statement | If_False | ? |
| 2 | 44 | If_Statement | If_True | ? |
| 3 | 152 | Slice_UnboundLower | Slice_Unbounded | ? |
| 4 | 152 | Slice_UnboundLower | Slice_UnboundUpper | ? |

### [crud.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 141 | None | True | ? |
| 2 | 141 | None | False | ? |
| 3 | 189 | None | False | ? |
| 4 | 189 | None | True | ? |

### [vector_store.py] — 1 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 220 | <class 'ast.Or'> | <class 'ast.And'> | ? |

### [repository.py] — 7 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 54 | <class 'ast.Mult'> | <class 'ast.Mod'> | ? |
| 2 | 54 | <class 'ast.Mult'> | <class 'ast.Pow'> | ? |
| 3 | 54 | <class 'ast.Mult'> | <class 'ast.FloorDiv'> | ? |
| 4 | 54 | <class 'ast.Mult'> | <class 'ast.Div'> | ? |
| 5 | 54 | <class 'ast.Mult'> | <class 'ast.Sub'> | ? |
| 6 | 54 | <class 'ast.Mult'> | <class 'ast.Add'> | ? |
| 7 | 31 | <class 'ast.Or'> | <class 'ast.And'> | ? |

### [repository_traversal.py] — 2 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 190 | None | True | ? |
| 2 | 190 | None | False | ? |

### [clustering.py] — 2 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 197 | <class 'ast.Gt'> | <class 'ast.GtE'> | ? |
| 2 | 224 | <class 'ast.Or'> | <class 'ast.And'> | ? |

### [activation.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 32 | None | False | ? |
| 2 | 32 | None | True | ? |
| 3 | 163 | None | True | ? |
| 4 | 163 | None | False | ? |

### [router.py] — 3 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 75 | <class 'ast.NotIn'> | <class 'ast.In'> | ? |
| 2 | 119 | None | False | ? |
| 3 | 119 | None | True | ? |

### [schema.py] — 2 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 137 | True | None | ? |
| 2 | 137 | True | False | ? |

### [temporal.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 146 | None | False | ? |
| 2 | 146 | None | True | ? |
| 3 | 147 | None | True | ? |
| 4 | 147 | None | False | ? |

### [embedding.py] — 3 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 45 | <class 'ast.Is'> | <class 'ast.IsNot'> | ? |
| 2 | 32 | None | True | ? |
| 3 | 32 | None | False | ? |

### [ontology.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 93 | None | True | ? |
| 2 | 93 | None | False | ? |
| 3 | 80 | None | False | ? |
| 4 | 80 | None | True | ? |

### [librarian.py] — 6 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 145 | <class 'ast.Sub'> | <class 'ast.FloorDiv'> | ? |
| 2 | 145 | <class 'ast.Sub'> | <class 'ast.Add'> | ? |
| 3 | 145 | <class 'ast.Sub'> | <class 'ast.Mult'> | ? |
| 4 | 145 | <class 'ast.Sub'> | <class 'ast.Mod'> | ? |
| 5 | 145 | <class 'ast.Sub'> | <class 'ast.Pow'> | ? |
| 6 | 145 | <class 'ast.Sub'> | <class 'ast.Div'> | ? |

### [crud_maintenance.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 33 | None | True | ? |
| 2 | 33 | None | False | ? |
| 3 | 13 | If_Statement | If_True | ? |
| 4 | 13 | If_Statement | If_False | ? |

### [server.py] — 1 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 176 | If_Statement | If_True | ? |

### [tools.py] — 2 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 64 | None | True | ? |
| 2 | 64 | None | False | ? |

### [tools_extra.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 135 | None | True | ? |
| 2 | 135 | None | False | ? |
| 3 | 132 | None | True | ? |
| 4 | 132 | None | False | ? |

### [graph_algorithms.py] — 7 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 62 | Slice_UnboundLower | Slice_UnboundUpper | ? |
| 2 | 62 | Slice_UnboundLower | Slice_Unbounded | ? |
| 3 | 33 | <class 'ast.Eq'> | <class 'ast.NotEq'> | ? |
| 4 | 33 | <class 'ast.Eq'> | <class 'ast.LtE'> | ? |
| 5 | 33 | <class 'ast.Eq'> | <class 'ast.Gt'> | ? |
| 6 | 33 | <class 'ast.Eq'> | <class 'ast.Lt'> | ? |
| 7 | 33 | <class 'ast.Eq'> | <class 'ast.GtE'> | ? |

### [interfaces.py] — 4 survivors

| # | Line | Original | Mutated | Classification |
|---|------|----------|---------|----------------|
| 1 | 41 | None | True | ? |
| 2 | 41 | None | False | ? |
| 3 | 23 | None | True | ? |
| 4 | 23 | None | False | ? |

## Modules Below 75% Kill Rate (P0)

- analysis.py: 0.0%
- crud.py: 0.0%
- vector_store.py: 0.0%
- repository.py: 0.0%
- repository_traversal.py: 0.0%
- clustering.py: 66.7%
- activation.py: 0.0%
- router.py: 0.0%
- schema.py: 0.0%
- temporal.py: 0.0%
- lock_manager.py: 50.0%
- embedding.py: 0.0%
- ontology.py: 0.0%
- librarian.py: 33.3%
- crud_maintenance.py: 0.0%
- tools.py: 0.0%
- tools_extra.py: 0.0%
- graph_algorithms.py: 0.0%
- interfaces.py: 0.0%

## Modules Completed vs Pending

| Status | Modules |
|--------|---------|
| Completed | analysis.py, crud.py, vector_store.py, repository.py, repository_queries.py, repository_traversal.py, clustering.py, activation.py, router.py, schema.py, temporal.py, lock_manager.py, embedding.py, ontology.py, librarian.py, crud_maintenance.py, context_manager.py, logging_config.py, server.py, tools.py, tools_extra.py, graph_algorithms.py, interfaces.py |
| Timeout/Pending | search.py (Clean Trial Failed), search_advanced.py (Clean Trial Failed), retry.py (Clean Trial Failed) |

## Bugs Discovered (DO NOT FIX — document only)

CRITICAL: Mutation testing inconclusive due to environmental/performance issues.
- **Total Timeouts:** 0
- **Total Errors:** 10
- The test suite takes ~140s to run (clean trial), exceeding the mutation timeout of 30s.
- Some tests rely on Redis, which is causing ConnectionRefusedError unless skipped.
- `retry.py` failed to complete due to overall timeout.
