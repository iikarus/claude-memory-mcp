# MCP Tool Reference

Complete reference for the **30 MCP tools** exposed by the Claude Memory system.

---

## Entity CRUD

### `create_entity`

Create a new entity in the memory graph.

| Param        | Type        | Default       | Description                                  |
| ------------ | ----------- | ------------- | -------------------------------------------- |
| `name`       | `str`       | required      | Entity name                                  |
| `node_type`  | `str`       | required      | Type (e.g. `Concept`, `Person`, `Procedure`) |
| `project_id` | `str`       | required      | Project scope                                |
| `properties` | `dict`      | `None`        | Arbitrary key-value metadata                 |
| `certainty`  | `str`       | `"confirmed"` | `confirmed`, `probable`, `speculative`       |
| `evidence`   | `list[str]` | `None`        | Evidence sources                             |

**Returns:** `EntityCommitReceipt` — `{id, name, warnings}`

### `update_entity`

Update properties of an existing entity.

| Param        | Type   | Default  |
| ------------ | ------ | -------- |
| `entity_id`  | `str`  | required |
| `properties` | `dict` | required |
| `reason`     | `str`  | `None`   |

**Returns:** `dict` — updated entity data

### `delete_entity`

Delete (or soft-delete) an entity.

| Param         | Type   | Default  |
| ------------- | ------ | -------- |
| `entity_id`   | `str`  | required |
| `reason`      | `str`  | required |
| `soft_delete` | `bool` | `True`   |

**Returns:** `{status: "deleted"}` or `{status: "archived"}`

---

## Relationship CRUD

### `create_relationship`

Create a directed edge between two entities.

| Param               | Type       | Default  |
| ------------------- | ---------- | -------- |
| `from_entity`       | `str`      | required |
| `to_entity`         | `str`      | required |
| `relationship_type` | `EdgeType` | required |
| `properties`        | `dict`     | `None`   |
| `confidence`        | `float`    | `1.0`    |
| `weight`            | `float`    | `1.0`    |

**EdgeType values:** `RELATED_TO`, `ENABLES`, `IMPLEMENTS`, `DEPENDS_ON`, `PRECEDED_BY`, etc.

**Returns:** `dict` — `{id, type, from, to}`

### `delete_relationship`

Delete a relationship by ID.

| Param             | Type  | Default  |
| ----------------- | ----- | -------- |
| `relationship_id` | `str` | required |
| `reason`          | `str` | required |

**Returns:** `{status: "deleted"}`

---

## Observations

### `add_observation`

Add an observation (fact, note) linked to an entity.

| Param       | Type        | Default       |
| ----------- | ----------- | ------------- |
| `entity_id` | `str`       | required      |
| `content`   | `str`       | required      |
| `certainty` | `str`       | `"confirmed"` |
| `evidence`  | `list[str]` | `None`        |

**Returns:** `dict` — `{id, content, entity_id}`

> [!NOTE]
> Observations are automatically embedded and upserted to the vector store (E-3).

---

## Search

### `search_memory`

Search for entities using vector similarity. Supports strategy routing and hybrid search (ADR-007).

| Param                  | Type   | Default  | Description                                                     |
| ---------------------- | ------ | -------- | --------------------------------------------------------------- |
| `query`                | `str`  | required | Search query text                                               |
| `project_id`           | `str`  | `None`   | Scope to project                                                |
| `limit`                | `int`  | `10`     | Max results                                                     |
| `offset`               | `int`  | `0`      | Pagination offset                                               |
| `mmr`                  | `bool` | `False`  | Maximal Marginal Relevance for diverse results                  |
| `strategy`             | `str`  | `None`   | Explicit strategy override                                      |
| `temporal_window_days` | `int`  | `7`      | Lookback window for temporal queries                            |
| `include_meta`         | `bool` | `False`  | Wrap results with temporal exhaustion metadata                  |

**Strategy values:** `semantic`, `associative`, `temporal`, `relational`, or `None` (hybrid default via intent classification). `auto` is deprecated and maps to hybrid.

**Returns:**
- Default: `list[SearchResult]` — `{id, name, score, node_type, retrieval_strategy, recency_score, vector_score, ...}`
- `include_meta=True` (temporal): `HybridSearchResponse` — `{results: [...], meta: {temporal_exhausted, temporal_window_days, suggestion}}`

### `search_associative`

Spreading-activation search through the knowledge graph. Combines vector similarity
with graph-based energy propagation.

| Param        | Type    | Default            |
| ------------ | ------- | ------------------ |
| `query`      | `str`   | required           |
| `limit`      | `int`   | `10`               |
| `project_id` | `str`   | `None`             |
| `decay`      | `float` | `0.6`              |
| `max_hops`   | `int`   | `3`                |
| `w_sim`      | `float` | env `W_SIMILARITY` |
| `w_act`      | `float` | env `W_ACTIVATION` |
| `w_sal`      | `float` | env `W_SALIENCE`   |
| `w_rec`      | `float` | env `W_RECENCY`    |

**Returns:** `list[dict]` — ranked results with composite scores

---

## Graph Traversal

### `get_neighbors`

Retrieve neighboring entities up to a certain depth.

| Param       | Type  | Default  |
| ----------- | ----- | -------- |
| `entity_id` | `str` | required |
| `depth`     | `int` | `1`      |
| `limit`     | `int` | `20`     |
| `offset`    | `int` | `0`      |

**Returns:** `list[dict]` — neighbor entities

### `traverse_path`

Find the shortest path between two entities.

| Param     | Type  | Default  |
| --------- | ----- | -------- |
| `from_id` | `str` | required |
| `to_id`   | `str` | required |

**Returns:** `list[dict]` — ordered path nodes

### `find_cross_domain_patterns`

Analyze the graph for non-obvious connections between disparate domains.

| Param       | Type  | Default  |
| ----------- | ----- | -------- |
| `entity_id` | `str` | required |
| `limit`     | `int` | `10`     |

**Returns:** `list[dict]` — pattern descriptions

### `get_evolution`

Retrieve the evolution (history/observations) of an entity over time.

| Param       | Type  | Default  |
| ----------- | ----- | -------- |
| `entity_id` | `str` | required |

**Returns:** `list[dict]` — chronological evolution entries

---

## Temporal

### `query_timeline`

Query entities within a time window, ordered chronologically.

| Param        | Type             | Default  |
| ------------ | ---------------- | -------- |
| `start`      | `str` (ISO 8601) | required |
| `end`        | `str` (ISO 8601) | required |
| `limit`      | `int`            | `20`     |
| `project_id` | `str`            | `None`   |

**Returns:** `list[dict]` — entities in time range

### `get_temporal_neighbors`

Find entities connected by temporal edges.

| Param       | Type  | Default  |
| ----------- | ----- | -------- |
| `entity_id` | `str` | required |
| `direction` | `str` | `"both"` |
| `limit`     | `int` | `10`     |

**Direction values:** `before`, `after`, `both`

**Returns:** `list[dict]` — temporal neighbors

### `get_bottles`

Query "Message in a Bottle" entities — timestamped notes to your future self.

| Param             | Type        | Default |
| ----------------- | ----------- | ------- |
| `limit`           | `int`       | `10`    |
| `search_text`     | `str`       | `None`  |
| `before_date`     | `str` (ISO) | `None`  |
| `after_date`      | `str` (ISO) | `None`  |
| `project_id`      | `str`       | `None`  |
| `include_content` | `bool`      | `False` |

> [!NOTE]
> `include_content=True` hydrates bottles with observation content (E-1).

**Returns:** `list[dict]` — bottle entities

### `point_in_time_query`

Execute a search considering only knowledge known before `as_of`.

| Param        | Type             | Default  |
| ------------ | ---------------- | -------- |
| `query_text` | `str`            | required |
| `as_of`      | `str` (ISO 8601) | required |

**Returns:** `list[dict]` — results filtered by temporal cutoff

---

## Sessions

### `start_session`

Start a new session context.

| Param        | Type  | Default  |
| ------------ | ----- | -------- |
| `project_id` | `str` | required |
| `focus`      | `str` | required |

**Returns:** `dict` — `{session_id, project_id, focus, started_at}`

### `end_session`

End a session and record summary.

| Param        | Type        | Default  |
| ------------ | ----------- | -------- |
| `session_id` | `str`       | required |
| `summary`    | `str`       | required |
| `outcomes`   | `list[str]` | `None`   |

**Returns:** `dict` — `{status, session_id}`

### `record_breakthrough`

Record a learning breakthrough linked to a session.

| Param               | Type        | Default  |
| ------------------- | ----------- | -------- |
| `name`              | `str`       | required |
| `moment`            | `str`       | required |
| `session_id`        | `str`       | required |
| `analogy_used`      | `str`       | `None`   |
| `concepts_unlocked` | `list[str]` | `None`   |

**Returns:** `dict` — `{id, name, moment}`

---

## Analysis & Health

### `graph_health`

Get graph health metrics.

**Returns:** `dict` — `{total_nodes, total_edges, density, orphan_count, avg_degree, communities}`

### `analyze_graph`

Run graph algorithms to find key entities or communities.

| Param       | Type  | Default      |
| ----------- | ----- | ------------ |
| `algorithm` | `str` | `"pagerank"` |

**Algorithm values:** `pagerank`, `louvain`

**Returns (pagerank):** `list[{name, rank}]`
**Returns (louvain):** `list[{community_id, members}]`

### `get_hologram`

Retrieve a connected subgraph ("hologram") relevant to a query.

| Param        | Type  | Default  |
| ------------ | ----- | -------- |
| `query`      | `str` | required |
| `depth`      | `int` | `1`      |
| `max_tokens` | `int` | `8000`   |

**Returns:** `dict` — `{nodes, edges, stats: {total_nodes, total_edges}}`

### `find_knowledge_gaps`

Find structural gaps: clusters that are semantically similar but poorly connected.

| Param            | Type    | Default |
| ---------------- | ------- | ------- |
| `min_similarity` | `float` | `0.7`   |
| `max_edges`      | `int`   | `2`     |
| `limit`          | `int`   | `10`    |

**Returns:** `list[dict]` — gap descriptions

### `system_diagnostics`

Unified system diagnostics — graph stats, vector stats, and split-brain check (E-5).

**Returns:** `dict` — `{graph: {total_nodes, total_edges, ...}, vector: {count, error}, split_brain: {status, graph_only_count, graph_only_ids}}`

> [!NOTE]
> `split_brain.status` is `ok` (consistent), `drift` (graph-only entities found), or `unavailable` (vector store unreachable).

### `reconnect`

Session reconnect — structured briefing for a returning agent (E-4).

| Param        | Type  | Default |
| ------------ | ----- | ------- |
| `project_id` | `str` | `None`  |
| `limit`      | `int` | `10`    |

**Returns:** `dict` — `{recent_entities: [...], health: {...}, window: {start, end}}`

---

## Lifecycle

### `archive_entity`

Archive an entity (logical soft-hide, status → `archived`).

| Param       | Type  | Default  |
| ----------- | ----- | -------- |
| `entity_id` | `str` | required |

**Returns:** `dict` — `{status: "archived"}`

### `prune_stale`

Hard-delete archived entities older than N days.

| Param  | Type  | Default |
| ------ | ----- | ------- |
| `days` | `int` | `30`    |

**Returns:** `dict` — `{pruned_count}`

---

## Ontology

### `create_memory_type`

Register a new memory type in the ontology.

| Param                 | Type        | Default  |
| --------------------- | ----------- | -------- |
| `name`                | `str`       | required |
| `description`         | `str`       | required |
| `required_properties` | `list[str]` | `None`   |

**Returns:** `dict` — `{name, description, required_properties}`

---

## Automation

### `run_librarian_cycle`

Trigger the Librarian Agent to cluster and consolidate memories.

**Returns:** `dict` — cycle report with consolidation results
