# ADR-001: Hybrid Graph + Vector Storage

**Status:** Accepted
**Date:** 2026-01-06
**Context:** The system needs both structured relationship queries (traversals, paths, communities) and semantic similarity search. A single store cannot serve both well.
**Decision:** Use FalkorDB (Redis-backed graph) for structured data and Qdrant for vector embeddings. Both stores are kept in sync via the repository layer.
**Consequences:**

- Split-brain drift is possible — mitigated by `system_diagnostics()` and `validate_brain.py`.
- Two containers to manage, but each excels at its job.
- `reembed_all.py` and `purge_ghost_vectors.py` exist for sync recovery.
