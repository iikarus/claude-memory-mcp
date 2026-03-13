# SPEC: Hybrid Search Unification

**Spec ID:** HYBRID-SEARCH-001
**ADR:** `docs/adr/007-hybrid-search-unification.md`
**Priority:** P0 — recurring production bug, second reported incident
**Implementer:** Antigravity (Gemini)
**Reviewers:** Claude (architect), Tabish (sign-off)

---

## 1. Problem Statement

`search_memory(strategy="auto")` routes queries through a keyword-based intent
classifier that dispatches to a single strategy. When the router picks temporal or
relational, results bypass Qdrant entirely and return with hardcoded `score=0.0`.

**Root cause:** `search.py:220-221` — dict-to-SearchResult conversion hardcodes scores.
**Impact:** Every Claude instance using `strategy="auto"` sees "embedding service
degraded" when it's actually the router silently bypassing vector search.

### Affected Code Paths

```
search_memory(strategy="auto")
  → _route_strategy_search()
    → router.classify() picks TEMPORAL or RELATIONAL
      → query_timeline() or traverse_path()
        → returns raw dicts, no vector scores
          → SearchResult(score=0.0, distance=0.0)  ← THE BUG
```

---

## 2. Architecture: Vector-First with Graph Enrichment

### 2.1 Core Principle

Every search starts with Qdrant. Graph signals enrich — they never replace.

### 2.2 New Default Search Flow (`strategy=None`)

```
search_memory(query, strategy=None)
  │
  ├─ STEP 1: Vector Search (always runs)
  │    embedder.encode(query) → vector_store.search()
  │    → base_results: list[VectorHit]  (id, score, payload)
  │
  ├─ STEP 2: Intent Detection (parallel with Step 1 if possible)
  │    router.classify(query) → detected_intent
  │    (This is classification ONLY — no dispatch)
  │
  ├─ STEP 3: Graph Enrichment (based on detected_intent)
  │    ├─ TEMPORAL  → query_timeline(window=7d) → temporal_results
  │    ├─ RELATIONAL → traverse_path(entities) → path_results
  │    ├─ ASSOCIATIVE → spread activation → activation_results
  │    └─ SEMANTIC → no enrichment needed (vector-only)
  │
  ├─ STEP 4: Merge
  │    ├─ For entities found in BOTH vector + graph:
  │    │    keep vector score, attach graph metadata as enrichment
  │    ├─ For entities found ONLY in graph:
  │    │    merge via RRF (see §3)
  │    └─ For entities found ONLY in vector:
  │         keep as-is (pure semantic results)
  │
  └─ STEP 5: Hydrate & Return
       Build SearchResult objects with enriched fields
```

### 2.3 Explicit Strategy Override (unchanged behavior, improved output)

When `strategy` is explicitly set to `"temporal"`, `"relational"`, `"associative"`,
or `"semantic"`, dispatch directly to that strategy's handler — same as today, BUT:

- Results MUST still populate `retrieval_strategy` field
- If the strategy is graph-only (temporal/relational), attempt a lightweight vector
  lookup for each returned entity ID to attach a real score. If the entity has no
  vector, set `score=0.0` and `retrieval_strategy="temporal"` (making the zero
  **intentional and labeled**, not silently misleading).

### 2.4 Kill `strategy="auto"`

- Remove `"auto"` as a valid value
- If a caller passes `strategy="auto"`, treat it as `strategy=None` (the new hybrid
  default) and log a deprecation warning
- Update MCP tool docstring to remove `"auto"` from valid values
- Update all CLAUDE.md files that recommend `strategy='auto'`

---

## 3. RRF Merge Algorithm

Reciprocal Rank Fusion merges ranked lists without score normalization.

### 3.1 Formula

For each entity `e` appearing in any result list:

```
rrf_score(e) = Σ  1 / (k + rank_i(e))
               i∈sources
```

Where:
- `k = 60` (standard RRF constant, dampens top-rank dominance)
- `rank_i(e)` = 1-indexed rank of entity `e` in source `i`
- If entity `e` does not appear in source `i`, that term is 0

### 3.2 Sources for RRF

| Source | When Active | Rank Basis |
|--------|-------------|------------|
| Vector search | Always | Cosine similarity (descending) |
| Temporal graph | Intent = TEMPORAL | Recency (most recent first) |
| Relational graph | Intent = RELATIONAL | Path distance (shortest first) |
| Associative spread | Intent = ASSOCIATIVE | Composite score (descending) |

### 3.3 Merge Rules

1. **Both sources have entity** → RRF score becomes primary `score`, vector cosine
   preserved in a separate field, graph metadata attached
2. **Vector-only entity** → `score` = vector cosine, no graph enrichment
3. **Graph-only entity** → `score` = RRF score (will be lower since only one source
   contributed), `retrieval_strategy` indicates graph-only origin

### 3.4 Implementation Location

New file: `src/claude_memory/merge.py`

```python
def rrf_merge(
    vector_results: list[dict],     # [{"_id": str, "_score": float, ...}]
    graph_results: list[dict],      # [{"id": str, ...}]  (from graph queries)
    *,
    k: int = 60,
    limit: int = 10,
) -> list[MergedResult]:
    """Reciprocal Rank Fusion merge of vector and graph result lists."""
    ...
```

Return type `MergedResult` (internal, not exposed via MCP):

```python
@dataclass
class MergedResult:
    entity_id: str
    rrf_score: float
    vector_score: float | None      # None if graph-only
    vector_rank: int | None
    graph_rank: int | None
    graph_metadata: dict             # temporal/relational/associative enrichment
    retrieval_sources: list[str]     # e.g. ["vector", "temporal"]
```

---

## 4. SearchResult Schema Changes

### 4.1 New Fields

Add to `schema.py` SearchResult model:

```python
class SearchResult(BaseModel):
    # --- existing fields (unchanged) ---
    id: str
    name: str
    node_type: str
    project_id: str
    content: str | None = None
    score: float                        # PRIMARY ranking score (cosine, RRF, or composite)
    distance: float                     # 1.0 - score (kept for backward compat)
    salience_score: float = 0.0
    observations: list[str] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)

    # --- new fields ---
    retrieval_strategy: str = Field(
        default="semantic",
        description="What generated this result: 'semantic', 'hybrid', 'temporal', "
                    "'relational', 'associative'"
    )
    recency_score: float = Field(
        default=0.0,
        description="0-1 exponential decay score. 1.0 = just created, 0.5 = ~7 days old, "
                    "0.0 = ancient. Populated for all results when timestamp available."
    )
    path_distance: int | None = Field(
        default=None,
        description="Graph hops from query anchor. Only populated for relational results."
    )
    activation_score: float = Field(
        default=0.0,
        description="Spreading activation energy. Only populated for associative results."
    )
    vector_score: float | None = Field(
        default=None,
        description="Raw cosine similarity from Qdrant. None if entity had no vector match."
    )
```

### 4.2 Score Semantics

| `retrieval_strategy` | `score` contains | `vector_score` | Other fields populated |
|---|---|---|---|
| `"semantic"` | cosine similarity | same as score | recency_score |
| `"hybrid"` | RRF composite | cosine (if found) | recency_score + strategy-specific |
| `"temporal"` | cosine or 0.0 (labeled) | cosine or None | recency_score |
| `"relational"` | cosine or 0.0 (labeled) | cosine or None | path_distance |
| `"associative"` | composite_score | cosine component | activation_score, recency_score |

### 4.3 Backward Compatibility

- `score` and `distance` retain their existing semantics for pure semantic searches
- New fields all have defaults — existing callers that destructure SearchResult won't break
- `model_dump()` output grows but extra fields are additive

---

## 5. Temporal Window Parameterization

### 5.1 MCP Tool Signature Update

```python
@mcp.tool()
async def search_memory(
    query: str,
    project_id: str | None = None,
    limit: int = 10,
    offset: int = 0,
    mmr: bool = False,
    strategy: str | None = None,
    temporal_window_days: int = 7,       # NEW — was hardcoded 30
) -> list[dict[str, Any]] | str:
```

### 5.2 Temporal Exhaustion Flag

When temporal enrichment returns fewer results than `limit` within the requested
window, add to the response metadata:

```python
# In the response (not per-result, but as a wrapper or final result):
{
    "results": [...],
    "meta": {
        "temporal_exhausted": true,       # fewer results than limit in window
        "temporal_window_days": 7,        # what was searched
        "temporal_result_count": 3,       # how many came from temporal
        "suggestion": "Widen temporal_window_days for more historical results"
    }
}
```

**Important design note:** The `meta` envelope is only returned when the default
path (hybrid) runs temporal enrichment. Explicit `strategy="semantic"` calls return
the flat list as before. This preserves backward compatibility while giving hybrid
callers actionable information.

### 5.3 Internal Changes to `_route_temporal`

```python
# router.py — _route_temporal
async def _route_temporal(
    self,
    service: Any,
    query: str,
    limit: int,
    project_id: str | None,
    temporal_window_days: int = 7,       # parameterized
) -> tuple[list[dict], bool]:            # returns (results, exhausted)
    params = TemporalQueryParams(
        start=datetime.now(UTC) - timedelta(days=temporal_window_days),
        end=datetime.now(UTC),
        limit=limit,
        project_id=project_id,
    )
    results = await service.query_timeline(params)
    exhausted = len(results) < limit
    return results, exhausted
```

### 5.4 Recency Score Calculation

Reuse the existing formula from `activation.py:136-153` but with adjusted half-life:

```python
# 7-day half-life (aligned with default window)
recency_score = 2 ** (-age_days / 7.0)
```

| Age | Score |
|-----|-------|
| Just now | ~1.0 |
| 1 day | 0.91 |
| 3 days | 0.74 |
| 7 days | 0.50 |
| 14 days | 0.25 |
| 30 days | 0.06 |

**Note:** The half-life in `activation.py` is currently 30 days. This spec does NOT
change the activation engine's half-life — only the recency_score field on
SearchResult uses the 7-day half-life. Keep them independent; they serve different
purposes.

---

## 6. File-by-File Implementation Guide

### 6.1 New Files

| File | Purpose |
|------|---------|
| `src/claude_memory/merge.py` | RRF merge algorithm + MergedResult dataclass |
| `tests/unit/test_merge.py` | Unit tests for RRF merge |
| `tests/unit/test_hybrid_search.py` | Integration tests for the new default search flow |

### 6.2 Modified Files

| File | Changes | Risk |
|------|---------|------|
| `src/claude_memory/schema.py` | Add 5 new fields to SearchResult | LOW — additive, defaults |
| `src/claude_memory/search.py` | Rewrite `search()` default path, remove `_route_strategy_search` auto logic, add hybrid pipeline | **HIGH** — core search flow |
| `src/claude_memory/router.py` | `classify()` becomes public utility, `route()` still used for explicit strategies. Remove auto intent logic | MEDIUM |
| `src/claude_memory/server.py` | Add `temporal_window_days` param, deprecation warning for `"auto"`, response envelope for hybrid | MEDIUM |
| `src/claude_memory/temporal.py` | `_route_temporal` accepts `temporal_window_days` param | LOW |
| `tests/unit/test_router.py` | Update tests for classify-only usage, remove auto-dispatch tests | MEDIUM |
| `tests/unit/test_search_associative.py` | Verify associative still works through explicit strategy path | LOW |
| `tests/gauntlet/test_hypothesis_router.py` | Update property tests for new classify behavior | LOW |

### 6.3 Untouched Files (verify no breakage)

| File | Why |
|------|-----|
| `activation.py` | Activation engine is unchanged — still used by associative path |
| `vector_store.py` | Qdrant interface unchanged |
| `repository_queries.py` | Graph queries unchanged |
| `search_advanced.py` | `search_associative` and `get_hologram` unchanged |

---

## 7. Revised `search()` Method — Pseudocode

```python
async def search(
    self,
    query: str,
    limit: int = 5,
    project_id: str | None = None,
    offset: int = 0,
    mmr: bool = False,
    strategy: str | None = None,
    deep: bool = False,
    temporal_window_days: int = 7,
) -> list[SearchResult] | HybridSearchResponse:

    # ── Handle explicit strategies (direct dispatch, no hybrid) ──
    if strategy is not None:
        if strategy == "auto":
            logger.warning("strategy='auto' is deprecated; using hybrid default")
            strategy = None  # fall through to hybrid
        else:
            return await self._direct_strategy_search(
                query, strategy, limit, project_id, temporal_window_days
            )

    # ── HYBRID DEFAULT PATH ──

    # Step 1: Vector search (always)
    vector_results = await self._execute_vector_search(
        query, limit, project_id, offset, mmr
    )

    # Step 2: Intent classification (no dispatch — classification only)
    detected_intent = self.router.classify(query)

    # Step 3: Graph enrichment (based on intent)
    graph_results = []
    temporal_exhausted = False

    if detected_intent == QueryIntent.TEMPORAL:
        graph_results, temporal_exhausted = await self._temporal_enrichment(
            query, limit, project_id, temporal_window_days
        )
    elif detected_intent == QueryIntent.RELATIONAL:
        graph_results = await self._relational_enrichment(query)
    elif detected_intent == QueryIntent.ASSOCIATIVE:
        graph_results = await self._associative_enrichment(
            query, limit, project_id
        )
    # SEMANTIC intent → no graph enrichment needed

    # Step 4: Merge
    if graph_results:
        merged = rrf_merge(vector_results, graph_results, k=60, limit=limit)
    else:
        merged = vector_only_results(vector_results, limit=limit)

    # Step 5: Hydrate
    search_results = await self._hydrate_merged_results(
        merged, detected_intent, deep
    )

    # Step 6: Populate recency scores (for all results)
    for result in search_results:
        result.recency_score = self._compute_recency(result, half_life_days=7)

    # Step 7: Build response
    if detected_intent == QueryIntent.TEMPORAL:
        return HybridSearchResponse(
            results=search_results,
            meta=TemporalMeta(
                temporal_exhausted=temporal_exhausted,
                temporal_window_days=temporal_window_days,
                temporal_result_count=len(graph_results),
            ),
        )

    return search_results
```

---

## 8. `_direct_strategy_search` — Explicit Strategies (Improved)

When a caller explicitly passes `strategy="temporal"` etc., they want that specific
source. But we still fix the score-0 problem:

```python
async def _direct_strategy_search(
    self,
    query: str,
    strategy: str,
    limit: int,
    project_id: str | None,
    temporal_window_days: int,
) -> list[SearchResult]:

    intent = QueryIntent(strategy)
    results = await self.router.route(
        query, self, intent=intent, limit=limit, project_id=project_id,
        temporal_window_days=temporal_window_days,
    )

    # Fix the score-0 problem for explicit graph strategies:
    # Attempt lightweight vector lookup for each entity to get a real score
    if intent in (QueryIntent.TEMPORAL, QueryIntent.RELATIONAL):
        results = await self._attach_vector_scores(results)

    # Tag all results with their retrieval strategy
    for r in results:
        if isinstance(r, SearchResult):
            r.retrieval_strategy = strategy

    return results
```

`_attach_vector_scores` does a batch vector lookup by entity ID (not a full search)
to see if these entities have stored vectors. If yes, compute cosine similarity to
the query vector. If no vector exists, leave `vector_score=None` and `score=0.0`
but with `retrieval_strategy` properly set so the caller knows why.

---

## 9. MCP Response Format

### 9.1 Standard Response (semantic, associative, relational)

```json
[
    {
        "id": "abc-123",
        "name": "Dragon Brain Architecture",
        "node_type": "Entity",
        "project_id": "claudes-house",
        "content": "Core memory system...",
        "score": 0.847,
        "distance": 0.153,
        "salience_score": 0.6,
        "retrieval_strategy": "semantic",
        "recency_score": 0.91,
        "path_distance": null,
        "activation_score": 0.0,
        "vector_score": 0.847,
        "observations": [],
        "relationships": []
    }
]
```

### 9.2 Hybrid Response (when temporal enrichment runs)

```json
{
    "results": [ ... ],
    "meta": {
        "temporal_exhausted": false,
        "temporal_window_days": 7,
        "temporal_result_count": 4,
        "suggestion": null
    }
}
```

When `temporal_exhausted` is true:
```json
{
    "results": [ ... ],
    "meta": {
        "temporal_exhausted": true,
        "temporal_window_days": 7,
        "temporal_result_count": 2,
        "suggestion": "Widen temporal_window_days for more historical results"
    }
}
```

### 9.3 Backward Compatibility Note

The response type changes from `list[dict]` to `list[dict] | dict` when temporal
meta is present. Callers that do `results = search_memory(...)` and iterate directly
will break if they get the dict envelope.

**Mitigation:** Only return the envelope when the caller explicitly opts in OR when
detected intent is TEMPORAL. Document this clearly. Consider: if this is too breaking,
an alternative is to add `_meta` as a special last element in the list, or return
meta only when a `include_meta=True` param is set. AG should evaluate and choose the
least-breaking approach.

---

## 10. Test Plan

### 10.1 Unit Tests (`tests/unit/test_merge.py`)

| Test | Assertion |
|------|-----------|
| RRF with two identical lists | Scores = 2/(k+rank), order preserved |
| RRF with disjoint lists | All entities present, single-source scores lower |
| RRF with partial overlap | Overlapping entities score higher than non-overlapping |
| RRF with empty graph list | Returns vector results unchanged |
| RRF with empty vector list | Returns graph results with RRF scores |
| RRF k parameter affects score distribution | Higher k = flatter distribution |
| RRF respects limit | Output length ≤ limit |

### 10.2 Unit Tests (`tests/unit/test_hybrid_search.py`)

| Test | Assertion |
|------|-----------|
| Default search (strategy=None) always hits vector store | Mock vector_store.search called |
| Temporal intent triggers graph enrichment | query_timeline called alongside vector |
| Relational intent triggers path enrichment | traverse_path called alongside vector |
| Associative intent triggers activation | search_associative called alongside vector |
| Semantic intent skips graph enrichment | Only vector_store.search called |
| Results have retrieval_strategy populated | Field is never empty/missing |
| Results have recency_score populated | Field is > 0 for recent entities |
| score is never hardcoded 0.0 for hybrid results | score > 0 when vector match exists |
| strategy="auto" logs deprecation, behaves as None | Warning logged, hybrid path runs |
| temporal_window_days=7 default | query_timeline uses 7-day window |
| temporal_exhausted flag correct | True when results < limit |

### 10.3 Updated Tests (`tests/unit/test_router.py`)

| Test | Assertion |
|------|-----------|
| classify() still works identically | No behavior change in classification |
| route() with explicit intent still dispatches | Direct strategy path works |
| route() is NOT called for strategy=None | Hybrid path uses classify() only |

### 10.4 Regression Tests

| Test | Assertion |
|------|-----------|
| Associative search via explicit strategy unchanged | composite_score flows through |
| get_hologram unchanged | Uses search() internally, verify it works |
| point_in_time_query unchanged | Separate code path, not affected |
| get_neighbors, traverse_path, get_evolution unchanged | Direct graph tools, not affected |
| MCP tool returns valid JSON | model_dump() works with new fields |

### 10.5 Gauntlet / Property Tests

| Test | Assertion |
|------|-----------|
| classify() fuzz: all outputs valid QueryIntent | Existing test, verify still passes |
| rrf_merge fuzz: random lists never crash | New property test |
| rrf_merge: score always ≥ 0 | Invariant |
| rrf_merge: output length ≤ limit | Invariant |

---

## 11. Migration & Rollout

### 11.1 Implementation Order

1. `schema.py` — Add new fields to SearchResult (safe, additive)
2. `merge.py` — New file, RRF algorithm (no dependencies)
3. `tests/unit/test_merge.py` — Test RRF in isolation
4. `router.py` — Make `classify()` a clean public API, update `_route_temporal` signature
5. `search.py` — Rewrite default search path to hybrid pipeline
6. `server.py` — Add `temporal_window_days`, deprecation warning, response envelope
7. `tests/unit/test_hybrid_search.py` — Full integration tests
8. Update existing tests in `test_router.py`, `test_search_associative.py`
9. Run full gauntlet (`pytest tests/`)

### 11.2 Post-Implementation

- Update `docs/MCP_TOOL_REFERENCE.md` with new params and response format
- Update `docs/USER_MANUAL.md` with hybrid search explanation
- Update all CLAUDE.md files: remove `strategy='auto'` recommendation, document
  `temporal_window_days`
- Update `CHANGELOG.md`

### 11.3 Rollback Plan

If hybrid search causes issues:
- The explicit strategy paths are preserved and unchanged
- Callers can switch to `strategy="semantic"` for pure vector search (always worked)
- The old `_route_strategy_search` behavior can be restored by reverting `search.py`

---

## 12. Open Questions for AG

1. **Response envelope vs flat list**: The temporal meta envelope breaks callers that
   iterate directly. Consider `include_meta=True` param or a `_meta` convention.
   Choose the least-breaking approach and document why.

2. **Parallelism in Step 1+2**: Can vector search and intent classification run
   concurrently via `asyncio.gather()`? Classification is CPU-only (regex), so it's
   fast — but measure if the overhead of gather is worth it.

3. **`_attach_vector_scores` batch efficiency**: For explicit temporal/relational
   strategies, we look up vectors by entity ID. Qdrant supports batch point retrieval
   (`retrieve_points`). Use that, not N individual lookups.

4. **Recency half-life config**: The 7-day half-life is hardcoded in this spec. Should
   it be configurable via env var like the activation weights? Lean toward yes for
   consistency, but don't over-engineer.

---

## 13. Success Criteria

- [ ] `search_memory(query="recent work")` returns results with `score > 0` and
      `retrieval_strategy="hybrid"`
- [ ] `search_memory(query="what is Dragon Brain?")` returns pure semantic results
      with `retrieval_strategy="semantic"`
- [ ] `search_memory(strategy="temporal")` returns results with `retrieval_strategy=
      "temporal"` and `vector_score` populated where possible
- [ ] `strategy="auto"` logs deprecation warning, behaves as hybrid default
- [ ] No existing test regressions
- [ ] All new tests pass
- [ ] `score=0.0` only appears when `vector_score=None` (entity genuinely has no
      vector) AND `retrieval_strategy` explains why
