# Claude Memory MCP Server regarding "The Exocortex"

> **Code Name**: Project Tesseract (Phase 12 Complete)
> **Status**: Production Ready (Dockerized)

A long-term memory system for Claude, built as a Model Context Protocol (MCP) server. It provides semantic storage, holographic retrieval, and autonomous maintenance ("The Librarian") using a Knowledge Graph backend.

## 🚀 Features

- **Memory Graph**: Stores entities, relationships, and observations in **FalkorDB** (Cypher + Vector).
- **Holographic Retrieval**: Retrieves not just nodes, but their full connected context ("The Hologram").
- **Autonomous Maintenance**: "The Librarian" agent runs periodically to cluster related memories and synthesize higher-order concepts.
- **Visual Dashboard**: A Streamlit UI to explore the memory graph interactively.
- **Strict Quality**: 100% Mypy typed, 100% Test Coverage on logic.

## 🛠️ Architecture

- **Backend**: `falkordb` (Graph) + `qdrant` (Vectors)
- **Server**: `mcp` (Model Context Protocol) via `FastMCP`
- **ML Layer**: `sentence-transformers` (`BAAI/bge-m3`) for 1024d embeddings.
- **Clustering**: `scikit-learn` (DBSCAN) for concept discovery.
- **Frontend**: `streamlit` for visualization.

## 🏁 Quick Start

### Option 1: Docker (Recommended)

One command to rule them all. Spins up Database, Server, and Dashboard.

```bash
docker-compose up --build
```

- **MCP Endpoint**: `http://localhost:8000/sse` (or stdio if configured)
- **Dashboard**: `http://localhost:8501`

### Option 2: Local Dev

1.  **Install Dependencies**:
    ```bash
    pip install .
    ```
2.  **Start Database** (You need a FalkorDB instance running on port 6379).
3.  **Run Server**:
    ```bash
    claude-memory
    ```
4.  **Run Dashboard**:
    ```bash
    streamlit run src/dashboard/app.py
    ```

## 📚 Documentation

Detailed manuals are located in `docs/`:

- [User Manual](docs/USER_MANUAL.md): How to use the tools with Claude.
- [Maintenance Manual](docs/MAINTENANCE_MANUAL.md): How to manage the system.
- [Code Inventory](docs/CODE_INVENTORY.md): Comprehensive file listing.
- [Architecture](docs/ARCHITECTURE.md): System design deep dive.

## 🛡️ "The Moto"

> "No code without a git pre commit + plethora of unit tests + mercenary checks."

This project adheres to strict validation rules found in `.pre-commit-config.yaml`.
