# Claude Memory MCP — CLAUDE.md

Drop this file into your project root or reference it from your Claude Code config to teach Claude how to use its persistent memory layer.

## What This Is

A persistent memory system for Claude. Knowledge graph (FalkorDB) + vector search (Qdrant) + MCP server. Claude can store entities, observations, and relationships — then recall them semantically across sessions.

## Setup Verification

At the start of every session, verify the memory system is running:

```
docker ps --filter "name=claude-memory"
```

You should see 4 healthy containers: graphdb, qdrant, embeddings, dashboard.

If MCP tools (`search_memory`, `create_entity`, etc.) are not available, the server may need restarting. MCP failures are **silent** — always verify tool availability at session start.

## Updating

```bash
cd claude-memory-mcp
git pull origin master
pip install -e ".[dev]"
```

If Docker images changed: `docker compose pull && docker compose up -d`

## How to Search

### Default (Hybrid Search — Recommended)

```
search_memory(query="your question here")
```

No strategy parameter needed. The default path:
1. Runs vector similarity search (always)
2. Detects query intent (temporal, relational, associative, or semantic)
3. Enriches results with graph signals based on detected intent
4. Merges via Reciprocal Rank Fusion if graph results found entities that vector search missed

### Explicit Strategies (When You Know What You Want)

| Strategy | When to Use | Example |
|----------|-------------|---------|
| `"semantic"` | Pure meaning-based similarity | `search_memory(query="distributed systems", strategy="semantic")` |
| `"temporal"` | Time-based queries | `search_memory(query="last week's work", strategy="temporal")` |
| `"relational"` | Path/connection queries (quote entity names) | `search_memory(query="path between \"Auth\" and \"Database\"", strategy="relational")` |
| `"associative"` | Spreading activation through the graph | `search_memory(query="related to authentication", strategy="associative")` |

### Temporal Window

Temporal queries default to a 7-day lookback. Widen if needed:

```
search_memory(query="recent progress", temporal_window_days=14)
```

Use `include_meta=True` to see if there are more results beyond the window:

```
search_memory(query="recent work", include_meta=True)
```

If the response includes `"temporal_exhausted": true`, widen the window for more history.

### Understanding Results

Each result includes:

| Field | Meaning |
|-------|---------|
| `score` | Primary ranking score (cosine similarity, RRF composite, or activation composite) |
| `retrieval_strategy` | What generated this result: `"semantic"`, `"hybrid"`, `"temporal"`, `"relational"`, `"associative"` |
| `vector_score` | Raw cosine similarity from Qdrant. `null` if entity had no vector match |
| `recency_score` | 0-1 exponential decay. 1.0 = just created, 0.5 = ~7 days old |
| `activation_score` | Spreading activation energy (associative results only) |
| `path_distance` | Graph hops from query anchor (relational results only) |
| `salience_score` | Entity importance/frequency score |

**Key insight:** If `score` is 0.0, check `retrieval_strategy` — it tells you why. A temporal-only result with no vector embedding will legitimately have `score=0.0` and `vector_score=null`.

## How to Store Memories

### Entities (Things)

```
create_entity(name="Project Alpha", node_type="Entity", project_id="my-project")
```

Common node types: `Entity`, `Concept`, `Person`, `Procedure`, `Session`

### Observations (Facts About Things)

```
add_observation(entity_id="<uuid>", content="This project uses a microservices architecture")
```

Observations are automatically embedded and indexed for semantic search.

### Relationships (Connections)

```
create_relationship(
    from_entity="<uuid>",
    to_entity="<uuid>",
    relationship_type="DEPENDS_ON"
)
```

Common edge types: `RELATED_TO`, `ENABLES`, `IMPLEMENTS`, `DEPENDS_ON`, `PRECEDED_BY`, `PART_OF`, `EVOLVED_FROM`, `SUPERSEDES`

**Wiring rule:** Every entity should have at least one relationship to another entity. Entities connected only to their observations are "near-orphans" — findable via search but invisible to graph traversal.

## How to Explore the Graph

| Tool | Purpose |
|------|---------|
| `get_neighbors(entity_id, depth=1)` | Find connected entities within N hops |
| `traverse_path(from_id, to_id)` | Shortest path between two entities |
| `get_evolution(entity_id)` | Chronological history of an entity's observations |
| `find_cross_domain_patterns(entity_id)` | Non-obvious connections across domains |
| `get_hologram(query, depth=1)` | Rich subgraph visualization around a topic |

## How to Track Time

| Tool | Purpose |
|------|---------|
| `query_timeline(start, end)` | Entities within a time window |
| `get_temporal_neighbors(entity_id)` | Entities connected by temporal edges |
| `point_in_time_query(query, as_of)` | "What did I know as of this date?" |
| `start_session(project_id, focus)` | Begin a tracked session |
| `end_session(session_id, summary)` | Close a session with outcomes |

## Health & Diagnostics

```
graph_health()          # Node/edge counts, orphans, density
system_diagnostics()    # Infrastructure status, embedding health
```

If `orphan_count > 0`, investigate before deleting — orphans may carry real data.

### Orphan Management

```
list_orphans(limit=50)   # See all orphan nodes for triage
```

### Drift Detection

```
search_stats()           # Rolling-window search behaviour stats (DRIFT-002)
```

Use `search_stats()` to monitor retrieval strategy distribution, score percentiles, and latency trends. Useful for detecting when something has drifted.

## Session Best Practices

1. **Start:** Verify containers are healthy. Run `search_memory(query="recent work")` to pick up context.
2. **During:** Log important learnings to the graph as you go. Autocompact can clear context without warning.
3. **End:** Create entities for key decisions/learnings. Update relationships. Check `graph_health()`.

## Common Pitfalls

- **MCP failures are silent.** If `search_memory` isn't available, the server may have crashed. Check Docker.
- **Don't pass `strategy="auto"`.** It's deprecated. Just omit the strategy parameter for hybrid search.
- **Observations need entities.** You can't create a free-floating observation — it must be attached to an entity.
- **Graph name is `claude_memory`**, not `dragon_brain` or anything else. If querying FalkorDB directly, use this name.
- **Subagents can't use MCP tools.** Never delegate memory operations to background agents — they don't have MCP access.
