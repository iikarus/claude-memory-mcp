# System Architecture

## Design Principles ("The Moto")

1.  **Mercenary Validation**: "No code without a git pre commit + plethora of unit tests + mercenary checks."
2.  **Strict Decoupling**: ML logic (`embedding.py`) is isolated from Business Logic (`tools.py`) via Dependency Injection.
3.  **Semantic Holiness**: We do not treat memories as strings. We treat them as **Holographic Graphs**.

## The Data Model

### Entities

Nodes in the graph (FalkorDB).

- **Properties**: `id`, `name`, `description`, `node_type`, `project_id`, `created_at`, `certainty`, `weight`.
- **Vector**: Stored in **Qdrant** (linked by `id`). Not on graph nodes.

### Vector Store (Qdrant)

High-performance vector similarity search.

- **Collection**: `memory_embeddings`
- **Payload**: Stores `entity_id` and embedding vector (1024d, BAAI/bge-m3).
- **Env**: `QDRANT_HOST` (default `localhost`, set to `qdrant` in Docker).

### Relationships

Edges in the graph.

- **Properties**: `confidence`, `weight` (0-1), `created_at`.
- **Typed**: `CONNECTED_TO`, `PART_OF`, `CAUSED`, `DEPENDS_ON`, `RELATES_TO`, `DERIVED_FROM`.

### The "Hologram"

A subgraph retrieval pattern.
Instead of `SELECT * FROM Memories WHERE text MATCH query`, we do:

1.  **Search**: Find anchors (top-k semantic match via Qdrant).
2.  **Expand**: BFS Traverse outward (Depth 2-3 via FalkorDB).
3.  **Return**: The connected subgraph (stripped of raw embeddings).

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
    H -->|reads vectors| I

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

- **Automated**: Windows Task Scheduler (`ExocortexDailyBackup`) runs daily at 3 AM.
- **Storage**: Local (`backups/`) + Google Drive (`G:\My Drive\exocortex_backups\`).
- **Retention**: Rolling 7-day window — both local and cloud copies.
- **Script**: `scripts/scheduled_backup.py`.

## Future Roadmap (V2+)

1.  **Authentication**: API key / token-based access control.
2.  **Multi-Tenancy**: Enforce `project_id` strictly at the Repo layer.
3.  **Recursive Summarization**: Librarian synthesizes concepts of concepts.
