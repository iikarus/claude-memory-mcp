# System Architecture

## Design Principles ("The Moto")

1.  **Mercenary Validation**: "No code without a git pre commit + plethora of unit tests + mercenary checks."
2.  **Strict Decoupling**: ML logic (`embedding.py`) is isolated from Business Logic (`tools.py`) via Dependency Injection.
3.  **Semantic Holiness**: We do not treat memories as strings. We treat them as **Holographic Graphs**.

## The Data Model

### Entities

Nodes in the graph (FalkorDB).

- **Properties**: `id`, `name`, `description`, `created_at`.
- **Vector**: Stored in Qdrant (linked by `id`).

### Vector Store (Qdrant)

High-performance vector similarity search.

- **Collection**: `memory_embeddings`
- **Payload**: Stores `entity_id` and embedding vector (1024d).

### Relationships

Edges in the graph.

- **Properties**: `confidence`, `created_at`.
- **Typed**: `CONNECTED_TO`, `PART_OF`, `CAUSED`, etc.

### The "Hologram"

A subgraph retrieval pattern.
Instead of `SELECT * FROM Memories WHERE text MATCH query`, we do:

1.  **Search**: Find anchors (top-k semantic match).
2.  **Expand**: BFS Traverse outward (Depth 2-3).
3.  **Return**: The connected subgraph.

### API Sanitization Layer ("The Bouncer")

Before any data leaves the `MemoryService` to return to the user/LLM:

- **Strip Embeddings**: We aggressively remove the `embedding` field (1024 floats) from all nodes.
- **Why**: Vectors are for machines (clustering/search), not for LLM context windows. Returning them wastes token budget (4KB/node) and degrades performance.

## Component Interaction

    A[MCP Human/Agent] -->|request| B[Server (FastMCP)]
    B -->|delegates| C[MemoryService]
    C -->|remote call| D[Embedding Microservice]
    C -->|persists| E[Repository]
    E -->|structure| F[(FalkorDB)]
    E -->|vectors| I[(Qdrant)]

    D -->|loads| M[Model (GPU)]

    G[LibrarianAgent] -->|monitors| C
    G -->|clusters| H[ClusteringService]
    H -->|reads vectors| I

## V2 Capabilities

1.  **Async Ingestion**: Salience updates run as background `asyncio` tasks with `flush_background_tasks()` for deterministic completion.
2.  **Multi-Tenancy**: `project_id` is enforced at the Repository layer across queries, traversals, and search filters.
3.  **Consolidation**: The Librarian agent clusters related nodes and synthesizes higher-order `Consolidated Memory` concepts.
