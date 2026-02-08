# User Manual: The Exocortex

This manual describes how to interact with the Claude Memory System. Last updated: February 2026.

## 🤖 For Claude (MCP Tools)

The system exposes the following tools via the Model Context Protocol (stdio transport).

### Core Memory Operations

- **`create_entity(name, node_type, project_id, properties, certainty, evidence)`**
  - Creates a new memory node with optional metadata.
  - _Example_: `create_entity("Project Tesseract", "Project", "tesseract", {"status": "active"})`
- **`add_observation(entity_id, content, certainty, evidence)`**
  - Adds a raw observation/note linked to an entity.
  - _Example_: `add_observation("123-abc", "The build failed due to missing wheel.")`
- **`update_entity(entity_id, properties, reason)`**
  - Updates an existing entity's properties.
- **`create_relationship(from_entity, to_entity, relationship_type, properties, confidence, weight)`**
  - Links two entities with a typed, weighted relationship.
  - _Example_: `create_relationship("node-A", "node-B", "DEPENDS_ON", weight=0.8)`
- **`delete_entity(entity_id, reason, soft_delete=True)`**
  - Soft-deletes (archives) or hard-deletes an entity.
- **`delete_relationship(relationship_id, reason)`**
  - Removes a relationship.

### Retrieval Tools (The Magic)

- **`search_memory(query, project_id, limit, offset)`**
  - Hybrid semantic search with pagination. Returns best matching nodes.
- **`get_neighbors(entity_id, depth=1, limit=20, offset=0)`**
  - Explore the graph. Returns the "Hologram" (connected context) around a node.
- **`traverse_path(from_id, to_id)`**
  - Finds the shortest path between two concepts.
- **`find_cross_domain_patterns(entity_id, limit=10)`**
  - Discovers non-obvious connections across disparate domains.
- **`get_evolution(entity_id)`**
  - Tracks the history/observations of an entity over time.
- **`point_in_time_query(query_text, as_of)`**
  - Time-travel search. "What did we know about X last week?"

### Session Management

- **`start_session(project_id, focus)`** — Opens a session context.
- **`end_session(session_id, summary, outcomes)`** — Closes and records.
- **`record_breakthrough(name, moment, session_id)`** — Captures learning moments.

### Maintenance

- **`run_librarian_cycle()`**
  - Triggers the Librarian Agent immediately. It clusters related memories and synthesizes higher-order concepts.
- **`create_memory_type(name, description, required_properties)`**
  - Registers a custom entity type in the runtime ontology.
- **`archive_entity(entity_id)`** — Logical hide.
- **`prune_stale(days=30)`** — Hard deletes archived entities older than N days.

## 🖥️ Visual Dashboard

Access the Streamlit UI at `http://localhost:8501`.

- **Search Tab**: Type a query to see a visual graph of results.
- **Stats Tab**: View system health, total node counts, and memory growth.
- **Explorer**:
  - **Graph View**: Interactively navigate the knowledge graph.
  - **Focus Node**: Filter the graph to show only a specific node and its immediate neighbors (1-2 hops).
  - **Limit**: Adjust the number of nodes rendered (Warning: High limits > 500 may slow down rendering).
  - **Text Filter**: Highlight nodes matching a specific regex pattern.

## 💾 Backups

### Automated (Active)

Daily at 3:00 AM → Google Drive (`G:\My Drive\exocortex_backups\`).
Rolling 7-day window. No action required.

### Manual

```powershell
# Create named snapshot
python scripts/backup_restore.py save --tag "before_experiment"

# Restore from snapshot
python scripts/backup_restore.py load "before_experiment"
docker compose down && docker compose up -d
```
