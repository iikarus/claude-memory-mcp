# Claude Memory MCP Server — "The Exocortex"

> **Status**: Production (Dockerized, Automated Backups)
> **Last Audit**: February 8, 2026 — 693 nodes, 797 edges, 255 tests, 100% coverage

A long-term memory system for Claude, built as a Model Context Protocol (MCP) server. It provides semantic storage, holographic retrieval, and autonomous maintenance ("The Librarian") using a Hybrid Graph+Vector backend.

## 🚀 Features

- **Memory Graph**: Stores entities, relationships, and observations in **FalkorDB** (Cypher queries).
- **Vector Search**: High-dimensional similarity search via **Qdrant** (1024d, BAAI/bge-m3).
- **Holographic Retrieval**: Retrieves not just nodes, but their full connected context ("The Hologram").
- **Autonomous Maintenance**: "The Librarian" agent clusters related memories and synthesizes higher-order concepts.
- **Visual Dashboard**: A Streamlit UI to explore the memory graph interactively.
- **Automated Backups**: Daily snapshots to Google Drive with rolling 7-day retention.
- **Strict Quality**: 100% Mypy typed, 100% Test Coverage, 255 unit tests.

## 🛠️ Architecture

- **Graph DB**: `FalkorDB` — structure, relationships, Cypher queries
- **Vector DB**: `Qdrant` — embeddings, similarity search
- **Embedding**: `sentence-transformers` (`BAAI/bge-m3`) via dedicated microservice
- **Server**: `FastMCP` — stdio transport (Claude Desktop / VS Code)
- **Clustering**: `scikit-learn` (DBSCAN) for concept discovery
- **Dashboard**: `Streamlit` for visualization
- **CI/CD**: `tox` (4 tiers: pulse, gate, hammer, polish)

## 🏁 Quick Start

### Docker (Recommended)

```powershell
docker compose up -d
```

Wait for healthchecks (~30s), then verify:

```powershell
docker compose ps   # All 4 should be "healthy"
```

- **Dashboard**: `http://localhost:8501`
- **Embedding API**: `http://localhost:8001` (Internal)
- **FalkorDB UI**: `http://localhost:3000`

### Local Dev

1.  **Install Dependencies**:
    ```powershell
    pip install -e .
    ```
2.  **Start Database** (FalkorDB on port 6379, Qdrant on port 6333).
3.  **Run Server**:
    ```powershell
    claude-memory
    ```
4.  **Run Dashboard**:
    ```powershell
    streamlit run src/dashboard/app.py
    ```

### Run Tests

```powershell
tox -e pulse    # lint + type check + 255 tests
```

## 📚 Documentation

Detailed manuals are located in `docs/`:

- [User Manual](docs/USER_MANUAL.md): How to use the tools with Claude.
- [Maintenance Manual](docs/MAINTENANCE_MANUAL.md): Backups, monitoring, troubleshooting.
- [Code Inventory](docs/CODE_INVENTORY.md): Comprehensive file listing.
- [Architecture](docs/ARCHITECTURE.md): System design deep dive.
- [Gotchas](docs/GOTCHAS.md): Known traps and subtleties.
- [Rehydration Document](docs/REHYDRATION_DOCUMENT.md): Onboarding guide for new agents.

## 🛡️ "The Moto"

> "No code without a git pre commit + plethora of unit tests + mercenary checks."

This project adheres to **The Gold Stack** — a 16-tool TDD/CI/CD suite. See `tox.ini` and `.pre-commit-config.yaml`.
