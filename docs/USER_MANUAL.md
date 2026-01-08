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
  - Standard semantic search. Returns individual matching nodes.
- **`get_hologram(query, depth=2)`**
  - **Best for Context**. Retrieves the search results AND their connected neighbors. Use this to understand the "situation".
- **`traverse_path(from, to)`**
  - Finds the shortest path between two concepts.
- **`point_in_time_query(query, as_of)`**
  - Time-travel search. "What did we know about X last week?"

### Maintenance (Manual)

- **`run_librarian_cycle()`**
  - Triggers the Librarian Agent immediately. It will find clusters of thoughts and consolidate them.

## 🖥️ Visual Dashboard

Structure your browsing via the Streamlit UI (`http://localhost:8501`).

- **Search Tab**: Type a query to see a visual graph of results.
- **Stats Tab**: View system health, total node counts, and memory growth.
- **Explorer**: Click on nodes in the graph to see their full properties and history.
