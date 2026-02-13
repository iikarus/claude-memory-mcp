# ADR-003: Python-Side Graph Algorithms

**Status:** Accepted
**Date:** 2026-02-08
**Context:** FalkorDB's built-in `algo.pageRank()` and community detection are limited. Early attempts used Cypher-based algorithms that were brittle and slow.
**Decision:** Run PageRank and Louvain community detection in Python using `networkx`, pulling the adjacency data from FalkorDB first.
**Consequences:**

- Algorithms are more robust and testable.
- Adds `networkx` dependency.
- Performance is acceptable for graphs under ~5000 nodes; for larger graphs, consider FalkorDB's native implementations if they mature.
