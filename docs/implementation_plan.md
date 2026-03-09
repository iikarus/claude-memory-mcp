# Implementation Plan - Claude Memory System (Hybrid Strategy)

**Goal**: Build a persistent, hybrid (Graph + Vector) memory system for Claude using a custom MCP server wrapper around `graphiti-core` and FalkorDB.

## User Review Required

> [!IMPORTANT] > **Hybrid Strategy Confirmation**: We are building a **custom Python MCP server** (`claude-memory-mcp`) that depends on `graphiti-core` from PyPI. This gives us control over schema extensions (Certainty, Breakthroughs) while leveraging Graphiti for heavy lifting.

> [!NOTE] > **Greenfield Deployment**: No migration from sqlite_vec. We will seed fresh data for Tabish, Claude, and initial session insights.

## Proposed Changes

### Infrastructure Layer

#### [NEW] [docker-compose.yml](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/docker-compose.yml)

- Defines `falkordb` service (valid for 14 days without license key).
- Exposes ports 6379 (Redis) and 3000 (UI).
- Persistent volume `claude_memory_data`.

### Application Layer (Custom MCP Server)

> [!NOTE] > **Architecture Change**: replaced `graphiti-core` wrapper with direct `falkordb` python client usage in `tools.py` due to connection incompatibilities. Adopted "Base Node Label" strategy (`:Entity`) to support unified vector indexing.

Directory: `claude-memory-mcp/`

#### [NEW] [pyproject.toml](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/pyproject.toml)

- Dependencies: `graphiti-core`, `falkordb`, `mcp`, `pydantic`, `sentence-transformers`.
- Dev Dependencies: `black`, `isort`, `ruff`, `mypy`, `pytest`, `pre-commit`.

#### [NEW] [src/claude_memory/server.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/server.py)

- Main entry point.
- Initializes `Graphiti` client.
- Exposes MCP tools.

#### [NEW] [src/claude_memory/tools.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/tools.py)

- Implements the "Thin Wrapper" logic.
- Custom tools: `record_breakthrough`, `add_observation` (with certainty), `search_memory` (hybrid).

#### [NEW] [src/claude_memory/schema.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/schema.py)

- Pydantic models for our custom node types (Breakthrough, Session, etc.).
- Defines strict Edge Types.

### Database Seeding

#### [NEW] [scripts/seed_initial_data.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/scripts/seed_initial_data.py)

- Connects to Graphiti.
- Creates "Meta" namespace.
- Seeds Tabish and Claude personas.
- Seeds initial project context.

## Verification Plan

### Automated Tests

Run via `pytest` in `claude-memory-mcp/`:

1.  **Unit**: Schema validation, Pydantic models.
2.  **Integration**: Connect to FalkorDB Docker, create/retrieve nodes, verify semantic search.
3.  **End-to-End**: Simulate full MCP conversation flow.

### Manual Verification

1.  **Docker Health**: `docker stats` to ensure FalkorDB is stable.
2.  **MCP Connection**: Use "MCP Inspector" or connecting via Claude Desktop config to verify tools are listed.
3.  **Functional Check**:
    - "Who is Tabish?" -> Should retrieve from Meta namespace.
    - "Record a breakthrough: 'Pipes and Valves'" -> Should create Breakthrough node.

## Phase 2: Full Spec Implementation

### Goal

Implement ALL missing functional requirements from `claude-memory-system-specs.md` and establish a rigorous testing harness.

### 1. Expanded Application Layer

#### [MODIFY] [src/claude_memory/tools.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/tools.py)

- **Entity Management**:
  - `add_observation(entity_id, content, certainty)`
  - `update_entity(entity_id, properties)`
  - `delete_entity(entity_id, reason)`
- **Relationship Management**:
  - `delete_relationship(relationship_id, reason)`
- **Session Management**:
  - `start_session(project_id, focus)`
  - `end_session(session_id, summary)`
- **Advanced Retrieval**:
  - `get_neighbors(entity_id, depth, limit)`
  - `traverse_path(from_id, to_id)`
  - `find_cross_domain_patterns(entity_id)` (Graph analysis)
- **Temporal & Maintenance**:
  - `get_evolution(entity_id)`
  - `point_in_time_query(query, as_of)`
  - `archive_entity(entity_id)`

#### [MODIFY] [src/claude_memory/server.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/server.py)

- Expose all new tools to MCP protocol.
- strict type definitions for all new tool arguments.

### 2. Operational Layer

#### [NEW] [scripts/operations.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/scripts/operations.py)

- Python script handling backup/restore logic (replacing PowerShell for cross-platform ease).
- `backup()`: Exports Graph + Index snapshots.
- `restore()`: Rehydrates from snapshot.
- `health_check()`: Verifies DB connectivity and Node counts.

### 3. Testing Layer (The "Plethora")

#### [NEW] [tests/unit/](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/tests/unit/)

- `test_entity_lifecycle.py`: Create, Update, Delete, Observation workflows.
- `test_session.py`: Start/End flows.
- `test_validation.py`: Strict schema enforcement.

#### [NEW] [tests/integration/](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/tests/integration/)

- `test_graph_traversal.py`: Verify neighbor finding and path traversal.
- `test_temporal.py`: Verify point-in-time queries.
- `test_full_workflow.py`: End-to-end "Day in the Life" simulation.

### Execution Order

1.  **Entity/Relationship Tools** (Foundation) -> Corresponding Unit Tests.
2.  **Session Tools** -> Unit Tests.
3.  **Search/Graph Tools** -> Integration Tests.
4.  **Temporal/Ops Tools** -> Integration Tests.
5.  **Final Polish** -> Full Suite Run.

## Phase 3: Optimization & CI/CD

### Goal

Establish production-grade reliability via automated pipelines and native vector indexing.

### 1. CI/CD Pipeline

#### [NEW] [.github/workflows/ci.yml](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/.github/workflows/ci.yml)

- **Triggers**: Push to `master`, Pull Requests.
- **Jobs**:
  - `lint`: Runs `pre-commit` (Black, Isort, Ruff, MyPy).
  - `test`:
    - Spins up `falkordb` container services.
    - Runs `pytest` against the ephemeral container.

### 2. Vector Indexing Refinement

#### [MODIFY] [src/claude_memory/tools.py](file:///c:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/src/claude_memory/tools.py)

- **Objective**: Replace "Brute Force" fallback with native FalkorDB Vector Index usage for scalability.
- **Action**:
  - Debug correct `db.idx.vector.createNodeIndex` syntax.
  - Verification: `test_graph_traversal.py` should pass using native index.

### Execution Order

1.  **CI/CD**: Create workflow file -> Verify it runs locally (simulated) or commit to trigger.
2.  **Vector Index**: Fix index creation -> Verify Search -> Disable Fallback.
