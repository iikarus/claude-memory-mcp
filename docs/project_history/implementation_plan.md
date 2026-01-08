# Implementation Plan - Phase 12: The Librarian

## Goal

Implement "The Librarian", an autonomous agent that runs periodically to cluster, synthesize, and organize memory nodes. This promotes long-term memory health and "Order from Chaos".

## User Review Required

> [!IMPORTANT] > **New Dependencies**: We are adding `scikit-learn` and `numpy` for clustering.
> **Breaking Change**: None anticipated, but `tools.py` consolidation logic will be heavily used.

## Proposed Changes

### Core Logic

#### [NEW] [clustering.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/clustering.py)

- **Role**: Encapsulates `scikit-learn` logic.
- **Methods**:
  - `cluster_nodes(nodes: List[Dict]) -> List[Cluster]`
  - Uses `DBSCAN` or `AgglomerativeClustering` on embedding vectors.

#### [NEW] [librarian.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/librarian.py)

- **Role**: The Agent Loop.
- **Methods**:
  - `run_cycle()`: The main maintenance loop.
  - `synthesize_cluster(cluster)`: Calls LLM (simulated or real) to generate summary.
  - `prune_memory()`: Calls `tools.prune_stale`.

#### [MODIFY] [server.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/server.py)

- Expose `run_librarian_cycle` as a tool (manually triggerable).

### Dependencies

#### [MODIFY] [pyproject.toml](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/pyproject.toml)

- Add `scikit-learn>=1.3.0`.
- Add `numpy`.

## Verification Plan

### Automated Tests

- **[NEW] test_clustering.py**: Verify DBSCAN groups vector points correctly.
- **[NEW] test_librarian.py**: Verify agent loop calls `consolidate_memories` when clusters are found.
- **Run**: `pytest tests/unit`

### Manual Verification

- Trigger `run_librarian_cycle` via MCP.
- Check logs for "Found X clusters".
- Verify new "Concept" nodes appear in the graph.
