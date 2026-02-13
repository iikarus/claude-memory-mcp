# ADR-004: Observation Vectorization (E-3)

**Status:** Accepted
**Date:** 2026-02-13
**Context:** Only entities were embedded in Qdrant. Observation content (the most granular knowledge) was invisible to vector search, limiting recall.
**Decision:** Embed observation content into Qdrant on creation (`crud_maintenance.py`). Vectors use payload `{name: content[:80], node_type: "Observation", entity_id, project_id}`. A backfill script (`embed_observations.py`) handles existing observations.
**Consequences:**

- Deep search can now find observations directly.
- Qdrant collection grows ~2x (entities + observations).
- `search()` excludes observations by default for backward compatibility; `deep=True` includes them.
