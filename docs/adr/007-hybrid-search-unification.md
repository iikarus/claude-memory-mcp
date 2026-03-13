# ADR-007: Hybrid Search Unification

**Status:** Accepted
**Date:** 2026-03-13
**Authors:** Tabish (decision), Claude (architecture), Antigravity (implementation)

## Context

`search_memory` with `strategy="auto"` routes queries through a keyword-based intent
classifier (`router.py`) that dispatches to one of four strategies: semantic, temporal,
relational, or associative. When the router picks temporal or relational, results come
back as raw dicts from FalkorDB graph queries — no vector similarity scores exist. The
dict-to-SearchResult conversion at `search.py:220-221` hardcodes `score=0.0` and
`distance=0.0` for all such results.

This means every Claude instance using `strategy="auto"` (the recommended default) gets
score-0 results whenever the query contains temporal/relational keywords — even though
Qdrant has valid embeddings for those entities. The embedding service appears broken when
it's actually the router silently bypassing it.

This is the second reported incident.

## Decision

1. **Vector-first architecture**: Every `search_memory` call starts with Qdrant vector
   search. Graph signals (temporal, relational, associative) become enrichment layers on
   top of results that already have real scores.

2. **Kill `strategy="auto"`**: The default path (`strategy=None`) becomes the hybrid
   path. Explicit strategies (`"temporal"`, `"relational"`, `"associative"`, `"semantic"`)
   remain as direct-access overrides.

3. **RRF merge** for graph-only entities that vector search missed but graph queries
   surfaced.

4. **Enriched SearchResult schema** with `retrieval_strategy`, `recency_score`,
   `path_distance`, `activation_score` fields.

5. **Parameterized temporal window**: default 7 days (was hardcoded 30), with
   `temporal_exhausted` flag for caller-driven expansion.

## Consequences

- `score` field on SearchResult always carries a meaningful value (cosine similarity or
  RRF composite) — never hardcoded 0.0
- Slightly higher latency for default searches (vector + intent detection + enrichment)
  but correctness >> speed here
- `strategy="auto"` is removed from the API; callers using it get a deprecation warning
  or should switch to `strategy=None`
- CLAUDE.md files need updating post-implementation to remove `strategy='auto'`
  recommendations
- Backward compatibility: explicit strategy values still work as direct dispatch
