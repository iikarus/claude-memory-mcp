# Claude Memory MCP Server — "The Exocortex"

> **Status**: Production (Dockerized, Automated Backups)
> **Last Audit**: February 14, 2026 — 700 nodes, 1253 edges, 463 tests, ~98% coverage

A long-term memory system for Claude, built as a Model Context Protocol (MCP) server. It provides semantic storage, holographic retrieval, spreading activation search, temporal reasoning, structural gap analysis, and autonomous maintenance ("The Librarian") using a Hybrid Graph+Vector backend.

## 🚀 Features

- **Memory Graph**: Stores entities, relationships, and observations in **FalkorDB** (Cypher queries).
- **Vector Search**: High-dimensional similarity search via **Qdrant** (1024d, BAAI/bge-m3, MMR diversity).
- **Holographic Retrieval**: Retrieves not just nodes, but their full connected context ("The Hologram").
- **Spreading Activation**: Graph-based energy propagation for associative, context-aware retrieval.
- **Temporal Reasoning**: Timeline queries, temporal neighbors, and time-travel search.
- **Adaptive Routing**: Automatic query intent classification (semantic, associative, temporal, relational).
- **Structural Gap Analysis**: InfraNodus-inspired detection of knowledge blind spots.
- **Autonomous Maintenance**: "The Librarian" agent clusters, consolidates, and detects gaps.
- **Visual Dashboard**: A Streamlit UI to explore the memory graph interactively.
- **Automated Backups**: Daily snapshots to Google Drive with rolling 7-day retention.
- **Strict Quality**: 100% Mypy typed, 463 unit tests, 5-tier Gold Stack CI/CD.
- **Strict Consistency**: Qdrant write failures always raise exceptions (split-brain prevention). No toggle.

## 🛠️ Architecture

- **Graph DB**: `FalkorDB` — structure, relationships, Cypher queries
- **Vector DB**: `Qdrant` — embeddings, similarity search, MMR
- **Embedding**: `sentence-transformers` (`BAAI/bge-m3`) via dedicated microservice
- **Server**: `FastMCP` — stdio transport (Claude Desktop / VS Code)
- **Clustering**: `scikit-learn` (DBSCAN) for concept discovery
- **Activation**: Spreading activation engine for associative retrieval
- **Routing**: Rule-based query intent classification
- **Dashboard**: `Streamlit` for visualization + diagnostics
- **CI/CD**: `tox` (5 tiers: pulse, gate, forge, hammer, polish)

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
tox -e pulse    # lint + type check + 463 tests
tox             # full Gold Stack (all 5 tiers)
```

## 📚 Documentation

Detailed manuals are located in `docs/`:

- [User Manual](docs/USER_MANUAL.md): How to use the 29 MCP tools with Claude.
- [MCP Tool Reference](docs/MCP_TOOL_REFERENCE.md): API reference — all 29 tools, params, return shapes.
- [Maintenance Manual](docs/MAINTENANCE_MANUAL.md): Backups, monitoring, troubleshooting.
- [Runbook](docs/RUNBOOK.md): 10 incident response recipes.
- [Code Inventory](docs/CODE_INVENTORY.md): Comprehensive file listing.
- [Architecture](docs/ARCHITECTURE.md): System design deep dive.
- [Gotchas](docs/GOTCHAS.md): Known traps and subtleties.
- [Rehydration Document](docs/REHYDRATION_DOCUMENT.md): Onboarding guide for new agents.
- [Upgrade Log](docs/UPGRADE_LOG.md): Phase-by-phase changelog of V2 enhancements.
- [Changelog](CHANGELOG.md): Release notes (Keep a Changelog format).
- [ADRs](docs/adr/): 6 Architecture Decision Records.
- [Docs Index](docs/DOCS_INDEX.md): **This master table of contents.**

## 🛡️ "The Moto"

> "No code without a git pre commit + plethora of unit tests + mercenary checks."

This project adheres to **The Gold Stack** — a 16-tool TDD/CI/CD suite across 5 tiers. See `tox.ini` and `.pre-commit-config.yaml`.
