# ADR-005: Associative Search with Spreading Activation

**Status:** Accepted
**Date:** 2026-02-08
**Context:** Pure vector similarity misses graph-connected knowledge. Users need a search mode that combines semantic similarity with structural relationships.
**Decision:** Implement spreading-activation search (`search_associative.py`) with configurable weights: `w_similarity`, `w_activation`, `w_salience`, `w_recency`. Energy decays across graph hops (`decay=0.6`, `max_hops=3`).
**Consequences:**

- Discovers non-obvious connections through the graph.
- Four tunable weights via environment variables.
- More expensive than pure vector search due to graph traversal.
