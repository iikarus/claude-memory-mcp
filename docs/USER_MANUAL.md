# User Manual: The Exocortex

This manual describes how to interact with the Claude Memory System.

## 🤖 For Claude (MCP Tools)

The system exposes the following tools via the Model Context Protocol.

### Core Memory Operations

- **`create_entity(name, node_type, project_id, properties)`**
  - Creates a new memory node.
  - _Example_: `create_entity("Project Tesseract", "Project", "tesseract", {"status": "active"})`
- **`add_observation(entity_id, content)`**
  - Adds a raw observation/note linked to an entity.
  - _Example_: `add_observation("123-abc", "The build failed due to missing wheel.")`
- **`update_entity(entity_id, properties)`**
  - Updates an existing entity.
- **`create_relationship(from, to, type)`**
  - Links two entities.
  - _Example_: `create_relationship("node-A", "node-B", "DEPENDS_ON")`

### Retrieval Tools (The Magic)

- **`search_memory(query)`**
  - Standard semantic search. Returns best matching nodes.
- **`get_neighbors(entity_id, depth=1, limit=20)`**
  - Explore the graph. Returns the "Hologram" (connected context) around a node.
- **`traverse_path(from_id, to_id)`**
  - Finds the shortest path between two concepts.
- **`find_cross_domain_patterns(entity_id, limit=10)`**
  - **The Sexy One**. Discovers non-obvious connections across disparate domains.
- **`get_evolution(entity_id)`**
  - Tracks the history/observations of an entity over time.
- **`point_in_time_query(query_text, as_of)`**
  - Time-travel search. "What did we know about X last week?"

### Maintenance (Manual)

- **`run_librarian_cycle()`**
  - Triggers the Librarian Agent immediately. It will find clusters of thoughts and consolidate them.

## 🖥️ Visual Dashboard

Structure your browsing via the Streamlit UI (`http://localhost:8501`).

- **Search Tab**: Type a query to see a visual graph of results.
- **Stats Tab**: View system health, total node counts, and memory growth.
- **Explorer**:
  - **Graph View**: Interactively navigate the knowledge graph.
  - **Focus Node**: Filter the graph to show only a specific node and its immediate neighbors (1-2 hops).
  - **Limit**: Adjust the number of nodes rendered (Warning: High limits > 500 may slow down rendering).
  - **Text Filter**: Highlight nodes matching a specific regex pattern.
