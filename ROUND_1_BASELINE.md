# Round 1: Iron Baseline — Dragon Brain Gauntlet
**Date:** 2026-02-24
**Runner:** Jules
**Repository:** claude-memory-mcp (master)

## Phase 1A: Gold Stack Results

| Tier | Status | Test Count | Time | Notes |
|------|--------|------------|------|-------|
| pulse | FAIL | 465 | >401s | Timed out. Manually ran tests: 459 passed, 4 errors. Coverage: 98% |
| gate | FAIL | 465 | 193s | ConnectionRefusedError: [Errno 111] Connection refused (Redis) |
| hammer | PASS | N/A | 11s | Security scan passed |
| polish | PASS | N/A | 181s | Codespell and Docstr-coverage passed |

## Phase 1B: Per-Module Coverage

```
Name                                        Stmts   Miss Branch BrPart  Cover   Missing
---------------------------------------------------------------------------------------
src/claude_memory/vector_store.py             119     17     30      1    87%   106-109, 248-250, 255-270
src/claude_memory/clustering.py               115      3     46      5    95%   137, 149->147, 156->153, 218, 225
src/claude_memory/analysis.py                 146      7     26      0    96%   49-50, 86-90
src/claude_memory/tools_extra.py               48      2      4      0    96%   179, 184
src/claude_memory/repository_queries.py        87      3     18      0    97%   249-251
src/claude_memory/librarian.py                 63      2      8      0    97%   124-125
src/claude_memory/graph_algorithms.py          46      0     26      2    97%   42->41, 101->100
src/claude_memory/search.py                   115      3     38      1    97%   89-91, 102
src/claude_memory/ontology.py                  44      1      6      0    98%   118
src/claude_memory/server.py                   103      2     14      0    98%   271, 281
src/dashboard/app.py                          112      2     26      0    99%   25-26
src/claude_memory/crud.py                     126      1     22      1    99%   47
src/claude_memory/__init__.py                   0      0      0      0   100%
src/claude_memory/activation.py                78      0     26      0   100%
src/claude_memory/context_manager.py           46      0      8      0   100%
src/claude_memory/crud_maintenance.py          37      0      2      0   100%
src/claude_memory/embedding.py                 51      0     12      0   100%
src/claude_memory/embedding_server.py          40      0      4      0   100%
src/claude_memory/interfaces.py                 1      0      0      0   100%
src/claude_memory/lock_manager.py             128      0     30      0   100%
src/claude_memory/logging_config.py            24      0      6      0   100%
src/claude_memory/repository.py                92      0     10      0   100%
src/claude_memory/repository_traversal.py      62      0     16      0   100%
src/claude_memory/retry.py                     48      0     10      0   100%
src/claude_memory/router.py                    57      0     18      0   100%
src/claude_memory/schema.py                    98      0      0      0   100%
src/claude_memory/search_advanced.py           52      0     14      0   100%
src/claude_memory/temporal.py                  40      0      8      0   100%
src/claude_memory/tools.py                     28      0      0      0   100%
---------------------------------------------------------------------------------------
TOTAL                                        2006     43    428     10    98%
```

### Modules Below 90% Coverage:
- src/claude_memory/vector_store.py: 87% (these are Round 4 mutation targets)

## Phase 1C: Test Inventory

| Metric | Count |
|--------|-------|
| Test functions | 486 |
| Test files | 46 |
| Total collected tests | 465 |

## Exit Criteria Assessment

- [ ] All 4 tox tiers pass
- [x] Coverage >= 90% branch
- [x] Test count >= 388
- [x] All baselines recorded
