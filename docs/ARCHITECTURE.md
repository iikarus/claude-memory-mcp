# System Architecture

## Design Principles ("The Moto")

1.  **Mercenary Validation**: "No code without a git pre commit + plethora of unit tests + mercenary checks."
2.  **Strict Decoupling**: ML logic (`embedding.py`, `activation.py`) is isolated from Business Logic (`tools.py`) via Dependency Injection.
3.  **Semantic Holiness**: We do not treat memories as strings. We treat them as **Holographic Graphs**.
4.  **Adaptive Retrieval**: Queries are automatically classified and routed to the best search strategy.

## The Data Model

### Entities

Nodes in the graph (FalkorDB).

- **Properties**: `id`, `name`, `description`, `node_type`, `project_id`, `created_at`, `occurred_at`, `certainty`, `weight`, `salience_score`, `last_accessed`.
- **Vector**: Stored in **Qdrant** (linked by `id`). Not on graph nodes.

### Vector Store (Qdrant)

High-performance vector similarity search.

- **Collection**: `memory_embeddings`
- **Payload**: Stores `entity_id` and embedding vector (1024d, BAAI/bge-m3).
- **Features**: MMR diversity search, HNSW optimized threshold (5000), full-text payload index on `name`.
- **Env**: `QDRANT_HOST` (default `localhost`, set to `qdrant` in Docker).

### Relationships

Edges in the graph.

- **Properties**: `confidence`, `weight` (0-1), `created_at`.
- **Typed**: `DEPENDS_ON`, `ENABLES`, `BLOCKS`, `CONTAINS`, `PART_OF`, `EVOLVED_FROM`, `SUPERSEDES`, `PRECEDED_BY`, `CONCURRENT_WITH`, `CONTRADICTS`, `SUPPORTS`, `REJECTED_FOR`, `REVISITED_BECAUSE`, `RHYMES_WITH`, `ANALOGOUS_TO`, `TAUGHT_THROUGH`, `BREAKTHROUGH_IN`, `UNLOCKED`, `CREATED_BY`, `DECIDED_IN`, `MENTIONED_IN`, `BELONGS_TO_PROJECT`, `BRIDGES_TO`, `RELATED_TO`.

### The "Hologram"

A subgraph retrieval pattern.
Instead of `SELECT * FROM Memories WHERE text MATCH query`, we do:

1.  **Search**: Find anchors (top-k semantic match via Qdrant).
2.  **Expand**: BFS Traverse outward (Depth 2-3 via FalkorDB).
3.  **Return**: The connected subgraph (stripped of raw embeddings).

### Spreading Activation

An associative retrieval pattern (Phase 12).

1.  **Seed**: Vector search finds initial anchors.
2.  **Activate**: Energy propagates through graph edges (decay=0.6, max_hops=3).
3.  **Inhibit**: Lateral inhibition (top-k) prevents runaway activation.
4.  **Rank**: Merge vector score + activation score + salience + recency with configurable weights.

### Adaptive Routing (Phase 13)

The `QueryRouter` classifies queries by intent:

- **SEMANTIC**: Factual lookups → vector search
- **ASSOCIATIVE**: "How does X relate to Y?" → spreading activation
- **TEMPORAL**: "What happened last week?" → timeline query
- **RELATIONAL**: "What depends on X?" → graph traversal

### Structural Gap Analysis (Phase 15)

InfraNodus-inspired knowledge gap detection:

1.  **Cluster**: DBSCAN groups related memories.
2.  **Compare**: Cosine similarity between cluster centroids.
3.  **Detect**: High similarity + low cross-edges = structural gap.
4.  **Report**: Generate research prompts + store `GapReport` entities.

### API Sanitization Layer ("The Bouncer")

Before any data leaves the `MemoryService` to return to the user/LLM:

- **Strip Embeddings**: We aggressively remove the `embedding` field (1024 floats) from all nodes.
- **Why**: Vectors are for machines (clustering/search), not for LLM context windows. Returning them wastes token budget (4KB/node) and degrades performance.

## Transport

- **stdio** (only). SSE transport was removed (Feb 2026). The MCP server runs via stdio for Claude Desktop / VS Code integration.

## Component Interaction

```
    A[MCP Human/Agent] -->|stdio| B[Server (FastMCP)]
    B -->|delegates| C[MemoryService]
    C -->|remote call| D[Embedding Microservice :8001]
    C -->|persists| E[Repository]
    E -->|structure| F[(FalkorDB :6379)]
    E -->|vectors| I[(Qdrant :6333)]

    D -->|loads| M[Model BAAI/bge-m3 (GPU)]

    G[LibrarianAgent] -->|monitors| C
    G -->|clusters| H[ClusteringService]
    G -->|detects gaps| H
    H -->|reads vectors| I

    K[ActivationEngine] -->|reads edges| F
    K -->|reads vectors| I

    L[QueryRouter] -->|classifies| C
    L -->|routes to| K

    J[Dashboard :8501] -->|imports| C
```

## Docker Services

| Service    | Image               | Ports (localhost-bound) | Healthcheck                          |
| ---------- | ------------------- | ----------------------- | ------------------------------------ |
| graphdb    | falkordb/falkordb   | 6379, 3000              | `redis-cli ping`                     |
| qdrant     | qdrant/qdrant       | 6333                    | `bash /dev/tcp/localhost/6333`       |
| embeddings | custom (Dockerfile) | 8001→8000               | `curl localhost:8000/health`         |
| dashboard  | custom (Dockerfile) | 8501                    | `curl localhost:8501/_stcore/health` |

All ports are bound to `127.0.0.1` — no external access.

## Backup Architecture

- **Automated**: Windows Task Scheduler (`ExocortexBackup`) runs daily at 3 AM.
- **Storage**: Local (`backups/`) + Google Drive (`G:\My Drive\exocortex_backups\`).
- **Retention**: Rolling 7-day window — both local and cloud copies.
- **Script**: `scripts/scheduled_backup.py`.

## CI/CD Tiers (The Gold Stack)

| Tier   | What                                                           |
| ------ | -------------------------------------------------------------- |
| pulse  | Ruff lint + format check + Mypy strict + Pytest (422 tests)    |
| gate   | Hypothesis property tests + diff-cover (changed-line coverage) |
| forge  | Mutation testing (mutatest — fault injection)                  |
| hammer | Security scanning (bandit, pip-audit, detect-secrets)          |
| polish | Codespell (typos) + docstr-coverage (docstring completeness)   |

Run all: `tox` | Run one: `tox -e pulse`
