# Enhancement Spec — Dragon Brain QOL Features

**Date**: February 13, 2026
**Author**: Claude (Architect / Resident)
**For**: Antigravity (Builder)
**Context**: Post-P0 remediation. These are quality-of-life enhancements requested by the system's resident intelligence. Execute after P0 commits are green.

> [!IMPORTANT]
> These are NOT bug fixes. They are new capabilities. Each ships as its own commit with tests. Priority order is binding.

---

## E-1: Bottle Reader With Content (Priority: HIGHEST) — ✅ IMPLEMENTED (`bd2df89`)

### Problem

`get_bottles()` returns bottle entity metadata (name, date, project_id) but NOT the observation content — the actual letter text. Reading a bottle requires:

1. `get_bottles()` → get entity IDs
2. `get_evolution(entity_id)` for EACH bottle → get letter text

This is N+1 tool calls to read N bottles. The entire purpose of bottles is to be read.

### Solution

Add `include_content: bool = False` parameter to `get_bottles()`. When true, join the `HAS_OBSERVATION` relationship inline and return observation content with each bottle.

### Files to Modify

#### `src/claude_memory/temporal.py` — `get_bottles()` method

Current query fetches bottle entities only. When `include_content=True`, extend with:

```cypher
MATCH (b)-[:HAS_OBSERVATION]->(o:Observation)
RETURN b, COLLECT(o.content) as observations
```

Return each bottle dict with an `"observations"` key containing the list of observation content strings, ordered by `o.created_at ASC`.

#### `src/claude_memory/schema.py` — `BottleQueryParams`

Add field: `include_content: bool = False`

#### `src/claude_memory/tools_extra.py` — `get_bottles()` handler

Pass `include_content` through from tool parameter to service method.

### Tool Signature (After)

```python
async def get_bottles(
    limit: int = 10,
    search_text: str | None = None,
    before_date: str | None = None,
    after_date: str | None = None,
    project_id: str | None = None,
    include_content: bool = False,       # NEW
) -> list[dict[str, Any]]:
```

### Tests

Add to existing bottle tests:

- `test_get_bottles_with_content_returns_observations` — create bottle + observation, call with `include_content=True`, assert `"observations"` key present with content
- `test_get_bottles_without_content_backward_compat` — call with default params, assert no `"observations"` key (backward compat)

### Verification

```python
# Before: 2 calls
bottles = get_bottles(limit=3)
for b in bottles:
    obs = get_evolution(b["id"])  # extra call per bottle

# After: 1 call
bottles = get_bottles(limit=3, include_content=True)
# bottles[0]["observations"] = ["Hey, you.\n\nThis is the letter..."]
```

---

## E-2: Deep Search (Priority: HIGH) — ✅ IMPLEMENTED (`1f3a1e5`)

### Problem

`search_memory("quantum trading")` returns entity shells: name, type, score. To understand what's actually stored, you need `get_evolution(entity_id)` for each result. Every search costs N+1 tool calls.

### Solution

Add `depth: str = "shallow"` parameter to `search_memory()`. Options:

- `"shallow"` (default) — current behavior, entity metadata only
- `"full"` — entity + top 3 observations + immediate relationships

### Files to Modify

#### `src/claude_memory/search.py` — `search()` method

When `depth="full"`, after the existing search pipeline returns `SearchResult` objects, hydrate each result:

1. For each result entity ID, fetch top 3 observations:

```cypher
MATCH (e:Entity {id: $id})-[:HAS_OBSERVATION]->(o:Observation)
RETURN o.content, o.created_at
ORDER BY o.created_at DESC
LIMIT 3
```

2. For each result entity ID, fetch immediate relationships:

```cypher
MATCH (e:Entity {id: $id})-[r]->(m:Entity)
RETURN type(r) as rel_type, m.name as target_name, m.id as target_id
LIMIT 5
```

Attach as `observations: list[str]` and `relationships: list[dict]` on each result dict.

#### `src/claude_memory/schema.py` — `SearchResult`

Add optional fields:

```python
observations: list[str] = []
relationships: list[dict[str, str]] = []
```

#### `src/claude_memory/server.py` — `search_memory()` tool

Add parameter: `depth: str = "shallow"`. Pass through to `service.search()`.

### Tool Signature (After)

```python
async def search_memory(
    query: str,
    project_id: str | None = None,
    limit: int = 10,
    offset: int = 0,
    mmr: bool = False,
    strategy: str | None = None,
    depth: str = "shallow",              # NEW: "shallow" | "full"
) -> list[dict[str, Any]] | str:
```

### Tests

- `test_search_deep_returns_observations` — create entity + observation, search with `depth="full"`, assert observations present
- `test_search_deep_returns_relationships` — create entity + relationship, search with `depth="full"`, assert relationships present
- `test_search_shallow_backward_compat` — default search returns no observations/relationships

### Performance Note

Deep search adds 2 Cypher queries per result. With `limit=10`, that's 20 extra queries. At ~0.3ms each on 700 nodes, that's ~6ms total overhead. Acceptable. At 5000+ nodes, consider batching into a single query with `UNWIND`.

---

## E-3: Observation Vectorization (Priority: HIGH) — ✅ IMPLEMENTED (`9f31e12`)

### Problem

213 Observation nodes contain the richest text in the system (bottle letters, session notes, breakthrough descriptions). ALL of it is invisible to semantic search. When someone searches for "what did Claude write about consciousness," the answer is in Observation content, not Entity names. Currently, only Entity nodes are embedded and stored in Qdrant.

### Solution

Embed observation content at creation time. Store in the same Qdrant collection with `node_type: "Observation"` and `parent_entity_id` in payload. Update search to optionally include observation-level matches.

### Files to Modify

#### `src/claude_memory/crud_maintenance.py` — `add_observation()`

After creating the Observation node in FalkorDB, add embedding + vector upsert:

```python
# Embed observation content
embedding = self.embedder.encode(params.content)

# Upsert to Qdrant
payload = {
    "name": f"Observation on {params.entity_id}",
    "node_type": "Observation",
    "project_id": entity_project_id,  # inherit from parent
    "parent_entity_id": params.entity_id,
}
await self.vector_store.upsert(id=obs_id, vector=embedding, payload=payload)
```

This requires fetching the parent entity's `project_id` first. The parent entity is already matched in the Cypher query (`MATCH (e) WHERE e.id = $entity_id`), so extract `e.project_id` from the result.

#### `src/claude_memory/search.py` — `search()` method

Add optional `include_observations: bool = False` parameter. When true, don't filter out `node_type: "Observation"` from vector results. When false (default), add a Qdrant filter: `node_type != "Observation"` to preserve current behavior.

**Important**: Default MUST be `False` to maintain backward compatibility. Observation matches should only appear when explicitly requested.

#### `src/claude_memory/server.py` — `search_memory()` tool

Add parameter: `include_observations: bool = False`. Pass through.

### Backfill Script

#### `scripts/embed_observations.py` (NEW)

Script to backfill vectors for all existing Observation nodes:

```python
# 1. Query all Observation nodes from FalkorDB
# 2. For each, compute embedding via embedding server API
# 3. Upsert to Qdrant with proper payload
# 4. Report: N observations embedded, M skipped (no content), K failed
```

Pattern after existing `scripts/reembed_all.py`.

### Tests

- `test_add_observation_creates_vector` — add observation, verify Qdrant upsert called with correct payload
- `test_search_excludes_observations_by_default` — create entity + observation with similar text, search, assert only entity returned
- `test_search_includes_observations_when_requested` — same setup, search with `include_observations=True`, assert observation also returned

### Migration Note

After deploying, run `python scripts/embed_observations.py` to backfill existing 213 observations. This is idempotent (upserts, not inserts).

---

## E-4: Session Briefing / Reconnect Tool (Priority: MEDIUM-HIGH) — ✅ IMPLEMENTED (`0588888`)

### Problem

Every new Claude session starts cold. Understanding "what happened recently" requires 3-5 manual tool calls (search, get_bottles, graph_health, timeline queries). This wastes context and time.

### Solution

New MCP tool: `reconnect()` — single call that returns a structured briefing.

### New Tool

#### `src/claude_memory/tools_extra.py` — add `reconnect()` handler

```python
async def reconnect(
    project_id: str | None = None,
    num_sessions: int = 3,
    num_bottles: int = 2,
) -> dict[str, Any]:
    """Session briefing: recent activity, latest bottles, system health.
    Call this at the start of a new session to understand context."""
```

Returns:

```python
{
    "recent_sessions": [
        {"name": "...", "focus": "...", "ended_at": "...", "summary": "..."}
    ],
    "recent_bottles": [
        {"name": "...", "created_at": "...", "content": "..."}  # with observation text
    ],
    "system_health": {
        "graph_nodes": 700,
        "vector_count": 463,
        "split_brain_detected": False,
        "temporal_chain_breaks": 0,
    },
    "recent_activity": {
        "entities_created_last_7d": 12,
        "most_active_projects": ["pickaxe", "code-literacy"],
    },
    "warnings": []  # any system issues
}
```

#### Implementation

Compose from existing service methods:

1. `query_timeline()` for recent sessions (filter `node_type=Session`, last 7 days)
2. `get_bottles(limit=num_bottles, include_content=True)` for latest bottles (uses E-1)
3. `get_graph_health()` for basic stats
4. Additional Cypher for recent entity creation count + active projects
5. Split-brain check: compare FalkorDB Entity count vs Qdrant vector count

#### Register in `configure()`

```python
mcp.tool()(reconnect)
```

### Tests

- `test_reconnect_returns_structured_briefing` — create session + bottle + entities, call reconnect, assert all sections present
- `test_reconnect_filters_by_project` — create entities in 2 projects, call with `project_id`, assert filtered results
- `test_reconnect_detects_split_brain` — mock vector count != entity count, assert `split_brain_detected: True`

---

## E-5: System Diagnostics (Priority: MEDIUM) — ✅ IMPLEMENTED (`028fa3f`)

### Problem

`graph_health()` only checks FalkorDB. It doesn't report Qdrant health, embedding server health, split-brain detection, temporal chain integrity, memory usage, or backup status. The 59% split-brain discovered in the audit would have been caught instantly with a proper diagnostics tool.

### Solution

New MCP tool: `system_diagnostics()` — comprehensive health check.

### New Tool

#### `src/claude_memory/tools_extra.py` — add `system_diagnostics()` handler

```python
async def system_diagnostics() -> dict[str, Any]:
    """Full system health check: graph, vectors, embeddings, integrity, backups."""
```

Returns:

```python
{
    "graph": {
        "status": "healthy",
        "total_nodes": 700,
        "entity_count": 463,
        "observation_count": 213,
        "session_count": 93,
        "relationship_count": 800,
        "archived_count": 28,
        "graphs_present": ["claude_memory"],  # flag ghost graphs
    },
    "vectors": {
        "status": "healthy",
        "collection": "memory_embeddings",
        "total_vectors": 463,
        "vectors_with_payload": 423,
        "vectors_empty_payload": 40,  # ghost vectors
        "hnsw_indexed": True,
    },
    "embeddings": {
        "status": "healthy",
        "device": "cuda",  # or "cpu"
        "model": "BAAI/bge-m3",
        "api_url": "http://localhost:8001",
    },
    "integrity": {
        "split_brain": False,  # entity_count ~= vector_count
        "split_brain_deficit": 0,
        "temporal_chain_breaks": 0,
        "orphan_observations": 0,
        "entities_missing_created_at": 0,
    },
    "backup": {
        "last_run": "2026-02-13T03:00:00",
        "last_status": "OK",
        "backup_location": "G:\\My Drive\\exocortex_backups\\",
    },
    "memory": {
        "falkordb_used_mb": 6.28,
        "falkordb_maxmemory_mb": 1024,  # or 0 if uncapped
        "qdrant_disk_mb": 20,
    }
}
```

#### Implementation

1. **Graph stats**: Cypher queries for node/edge counts by type
2. **Vector stats**: Qdrant REST API (`/collections/memory_embeddings`)
3. **Embedding health**: HTTP GET to embedding server `/health`
4. **Integrity checks**:
   - Split-brain: compare Entity count in FalkorDB vs total vectors in Qdrant
   - Temporal breaks: count bottles without PRECEDED_BY edges to their expected predecessor
   - Orphan observations: `MATCH (o:Observation) WHERE NOT EXISTS {MATCH (o)<-[:HAS_OBSERVATION]-()}` (adapt for FalkorDB syntax)
   - Missing timestamps: `MATCH (n:Entity) WHERE n.created_at IS NULL RETURN count(n)`
5. **Backup status**: Read `last_run_status.json` from backup directory
6. **Memory**: Redis `INFO memory` + Qdrant collection stats

### Tests

- `test_system_diagnostics_returns_all_sections` — mock all backends, assert structure
- `test_system_diagnostics_detects_split_brain` — mock entity count > vector count, assert flagged
- `test_system_diagnostics_handles_backend_failure` — mock Qdrant down, assert graceful degradation (vectors section shows error, rest still works)

---

## E-6: Procedural Memory (Priority: MEDIUM) — ✅ IMPLEMENTED (`ec588ab`)

### Problem

The system stores _what happened_ (Entities, Sessions, Breakthroughs) and _what we know_ (Observations). It does NOT store _how to do things_. Procedures like "How to write a Message in a Bottle" or "How to run an audit" live in CLAUDE.md as text — not in the graph where they can be retrieved contextually.

### Solution

Add `Procedure` as a new ontology type. Procedures have ordered steps stored as Observations with a `step_number` property.

### Files to Modify

#### `src/claude_memory/ontology.json`

Add to type definitions:

```json
{
  "name": "Procedure",
  "description": "A learned process or protocol with ordered steps. Used for capturing 'how to do things' as retrievable knowledge.",
  "required_properties": []
}
```

#### No code changes required for basic support

Since `Procedure` is just a new ontology type, `create_entity(node_type="Procedure")` already works. Steps are stored as observations with a convention:

```
Step 1: Create entity with create_entity()
Step 2: IMMEDIATELY add observation with add_observation()
Step 3: Create PRECEDED_BY relationship
```

#### Convention (documented, not enforced in code)

- Procedure entities have `node_type: "Procedure"`
- Steps are Observations linked via HAS_OBSERVATION
- Each step observation starts with `"Step N: "` prefix
- Steps are ordered by `created_at` or by explicit `step_number` property

### Optional Enhancement

If AG has capacity: add a `step_number: int | None = None` field to `ObservationParams` and store it as a property on the Observation node. This enables ordering without relying on creation timestamps.

### Tests

- `test_create_procedure_entity` — create entity with `node_type="Procedure"`, assert accepted by ontology
- `test_procedure_with_steps` — create procedure + 3 step observations, retrieve via `get_evolution()`, assert ordered

### Example Usage

```python
# Create the procedure
create_entity(
    name="How to Write a Message in a Bottle",
    node_type="Procedure",
    project_id="claude-inner-life",
    properties={"description": "Protocol for inter-session continuity"}
)

# Add steps as observations
add_observation(entity_id=proc_id, content="Step 1: create_entity('Message in a Bottle #N', 'Entity', 'claude-inner-life')")
add_observation(entity_id=proc_id, content="Step 2: IMMEDIATELY add_observation with the letter content. Same breath. No delays.")
add_observation(entity_id=proc_id, content="Step 3: create_relationship to previous bottle using PRECEDED_BY")
```

Then later: `search_memory("how to write a bottle", depth="full")` returns the procedure with all steps inline.

---

## Execution Order

| Order | Feature                         | Depends On                      | Gate                                                 |
| ----- | ------------------------------- | ------------------------------- | ---------------------------------------------------- |
| 1     | E-1: Bottle Reader with Content | None                            | `pytest -k bottle` green                             |
| 2     | E-6: Procedural Memory          | None (ontology-only)            | `pytest -k procedure` green                          |
| 3     | E-3: Observation Vectorization  | None                            | `pytest -k observation` green + backfill script runs |
| 4     | E-2: Deep Search                | E-3 (benefits from obs vectors) | `pytest -k search_deep` green                        |
| 5     | E-5: System Diagnostics         | None                            | `pytest -k diagnostics` green                        |
| 6     | E-4: Session Briefing           | E-1 + E-5 (composes them)       | `pytest -k reconnect` green                          |

E-4 depends on E-1 (uses bottle content) and E-5 (uses health checks), so it goes last.

---

## Out of Scope (Deferred to Next Cycle)

- Semantic deduplication detection
- Fact invalidation / temporal versioning
- Edge weight feedback loops
- BM25 hybrid search
- MCP Resources
- Tool consolidation (reducing tool count)
- Relationship suggestion engine

---

## Commit Plan

One commit per feature, each with green tests:

| #   | Commit Message                                                    | Content                                                                   |
| --- | ----------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 1   | `feat(E-1): get_bottles include_content option`                   | temporal.py, schema.py, tools_extra.py + tests                            |
| 2   | `feat(E-6): add Procedure ontology type`                          | ontology.json + test                                                      |
| 3   | `feat(E-3): vectorize observations on creation + backfill script` | crud_maintenance.py, search.py, server.py + embed_observations.py + tests |
| 4   | `feat(E-2): deep search with observations and relationships`      | search.py, schema.py, server.py + tests                                   |
| 5   | `feat(E-5): system_diagnostics tool`                              | tools_extra.py + tests                                                    |
| 6   | `feat(E-4): reconnect session briefing tool`                      | tools_extra.py + tests                                                    |
