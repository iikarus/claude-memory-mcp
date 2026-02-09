"""FalkorDB data access layer — Cypher queries, node/edge CRUD, and index management."""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from falkordb import FalkorDB

from claude_memory.retry import retry_on_transient

logger = logging.getLogger(__name__)


class MemoryRepository:
    """
    Data Access Layer for FalkorDB.
    Handles all direct database interactions, Cypher queries, and Index management.
    """

    def __init__(
        self, host: str | None = None, port: int | None = None, password: str | None = None
    ) -> None:
        """Connect to FalkorDB using host, port, and password from args or env vars."""
        self.host = host or os.getenv("FALKORDB_HOST", "localhost")
        self.port = port or int(os.getenv("FALKORDB_PORT", "6379"))
        self.password = password or os.getenv("FALKORDB_PASSWORD")

        self.client = FalkorDB(
            host=self.host,
            port=self.port,
            password=self.password,
        )
        self.graph_name = "claude_memory"

    @retry_on_transient()
    def select_graph(self) -> Any:
        """Return the active FalkorDB graph handle."""
        return self.client.select_graph(self.graph_name)

    def ensure_indices(self) -> None:
        """Create necessary indices if they don't exist."""
        # No longer manages vector indices.
        # Could add index on 'id' or 'name' for speed if not implicit in Node Key.
        pass

    @retry_on_transient()
    def create_node(self, label: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Creates a node (embedding logic moved to VectorStore)."""
        graph = self.select_graph()
        props = properties.copy()

        # Build query
        params: dict[str, Any] = {"props": props}

        # MERGE to prevent duplicates
        params["name"] = props.get("name")
        params["project_id"] = props.get("project_id")
        params["updated_at"] = props.get("updated_at")

        query = f"""
        MERGE (n:{label}:Entity {{name: $name, project_id: $project_id}})
        ON CREATE SET n = $props
        ON MATCH SET n.updated_at = $updated_at
        RETURN n
        """

        result = graph.query(query, params)
        return result.result_set[0][0].properties  # type: ignore

    @retry_on_transient()
    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieves a node by its ID."""
        graph = self.select_graph()
        query = "MATCH (n) WHERE n.id = $id RETURN n"
        result = graph.query(query, {"id": node_id})

        if not result.result_set:
            return None

        return result.result_set[0][0].properties  # type: ignore

    @retry_on_transient()
    def update_node(self, node_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Updates a node's properties."""
        graph = self.select_graph()
        props = properties.copy()

        query_parts = []
        query_parts.append("MATCH (n:Entity {id: $id})")
        query_parts.append("SET n += $props")
        query_parts.append("RETURN n")

        query = "\n".join(query_parts)
        params = {"id": node_id, "props": props}

        result = graph.query(query, params)
        if not result.result_set:
            return {}
        return result.result_set[0][0].properties  # type: ignore

    def delete_node(
        self, node_id: str, soft_delete: bool = False, reason: str | None = None
    ) -> bool:
        """Deletes a node (hard or soft)."""
        graph = self.select_graph()

        if soft_delete:
            query = (
                "MATCH (n) WHERE n.id = $id SET n.deleted = true, "
                "n.deletion_reason = $reason RETURN n"
            )
            res = graph.query(query, {"id": node_id, "reason": reason})
            return bool(res.result_set)
        else:
            query = "MATCH (n) WHERE n.id = $id DETACH DELETE n"
            graph.query(query, {"id": node_id})
            return True

    def create_edge(
        self, from_id: str, to_id: str, relation_type: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        """Creates a relationship between two nodes."""
        graph = self.select_graph()

        query = f"""
        MATCH (a), (b)
        WHERE a.id = $from AND b.id = $to
        CREATE (a)-[r:{relation_type}]->(b)
        SET r = $props
        RETURN r
        """
        result = graph.query(query, {"from": from_id, "to": to_id, "props": properties})
        if not result.result_set:
            return {}
        return result.result_set[0][0].properties  # type: ignore

    def delete_edge(self, edge_id: str) -> bool:
        """Deletes a relationship by ID."""
        graph = self.select_graph()
        query = "MATCH ()-[r]->() WHERE r.id = $id DELETE r"
        graph.query(query, {"id": edge_id})
        return True

    @retry_on_transient()
    def execute_cypher(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Executes a raw Cypher query."""
        graph = self.select_graph()
        return graph.query(query, params or {})

    @retry_on_transient()
    def get_subgraph(self, start_node_ids: list[str], depth: int = 1) -> dict[str, Any]:
        """Retrieves a subgraph of connected nodes up to 'depth' hops from start nodes."""
        if not start_node_ids:
            return {"nodes": [], "edges": []}

        graph = self.select_graph()

        # Optimization: If depth is 0, just fetch nodes directly (Fixes UNWIND bug on empty paths)
        if depth == 0:
            query_nodes = """
            MATCH (n:Entity) WHERE n.id IN $ids
            RETURN collect(distinct {
                id: n.id,
                labels: labels(n),
                properties: properties(n)
            }) as nodes
            """
            res_nodes = graph.query(query_nodes, {"ids": start_node_ids})
            if res_nodes.result_set:
                # Extract inner dict properties
                return {
                    "nodes": [n["properties"] for n in res_nodes.result_set[0][0]],
                    "edges": [],
                }
            return {"nodes": [], "edges": []}

        # Variable length path query
        # We find paths from root set to neighbors
        # We manually unroll the depth in Cypher or use variable length path
        # Note: [*1..2] syntax.

        query = f"""
        MATCH (root:Entity)
        WHERE root.id IN $ids
        CALL {{
            WITH root
            MATCH path = (root)-[*0..{depth}]-(neighbor)
            RETURN path
        }}
        RETURN path
        """

        # Note: FalkorDB might behave differently with CALL {}; simpler version:
        # MATCH path = (root:Entity)-[*0..depth]-(neighbor) WHERE root.id IN $ids RETURN path
        # But larger depth might explode. 'limit' helps?
        # User implementation plan didn't specify limit but implicit safety needed.
        # Let's use simple match for V1.

        query = f"""
        MATCH path = (root:Entity)-[*0..{depth}]-(neighbor)
        WHERE root.id IN $ids
        RETURN path
        """

        # Safer Query returning distinct nodes and edges as Maps for consistent parsing
        # We use {{ and }} to escape braces in f-string
        query = f"""
        MATCH path = (root:Entity)-[*0..{depth}]-(neighbor)
        WHERE root.id IN $ids
        UNWIND relationships(path) as r
        WITH distinct r, startNode(r) as s, endNode(r) as e
        RETURN collect(distinct {{
            id: r.id,
            source: s.id,
            target: e.id,
            type: type(r),
            properties: properties(r)
        }}) as edges,
        collect(distinct {{
            id: s.id,
            labels: labels(s),
            properties: properties(s)
        }}) + collect(distinct {{
            id: e.id,
            labels: labels(e),
            properties: properties(e)
        }}) as nodes
        """

        result = graph.query(query, {"ids": start_node_ids})

        # Now we parse the JSON-like maps returned
        if not result.result_set:
            # It might be empty if 0 hops and no edges?
            # Fallback for isolated nodes (depth 0)
            query_nodes = """
             MATCH (n:Entity) WHERE n.id IN $ids
             RETURN collect(distinct {
                id: n.id,
                labels: labels(n),
                properties: properties(n)
             }) as nodes
             """
            res_nodes = graph.query(query_nodes, {"ids": start_node_ids})
            if res_nodes.result_set:
                return {
                    "nodes": [n["properties"] for n in res_nodes.result_set[0][0]],
                    "edges": [],
                }
            return {"nodes": [], "edges": []}

        row = result.result_set[0]
        edges_data = row[0]
        nodes_data = row[1]

        # Deduplicate nodes by ID (Cypher set might not be perfect with maps)
        unique_nodes = {n["id"]: n["properties"] for n in nodes_data}
        unique_edges = {e["id"]: e for e in edges_data}  # e has source/target/type merged in

        return {"nodes": list(unique_nodes.values()), "edges": list(unique_edges.values())}

    def get_all_nodes(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Retrieves all entity nodes for clustering."""
        graph = self.select_graph()
        query = """
        MATCH (n:Entity)
        RETURN n
        LIMIT $limit
        """
        result = graph.query(query, {"limit": limit})
        return [row[0].properties for row in result.result_set]

    def get_total_node_count(self) -> int:
        """Returns the total number of nodes in the graph (for receipts)."""
        graph = self.select_graph()
        query = "MATCH (n) RETURN count(n)"
        result = graph.query(query)
        if not result.result_set:
            return 0
        return int(result.result_set[0][0])

    @retry_on_transient()
    def increment_salience(self, node_ids: list[str]) -> list[dict[str, Any]]:
        """Atomically increment retrieval_count and recalculate salience_score for nodes.

        Formula: salience_score = 1.0 + log2(1 + retrieval_count)
        This gives diminishing returns — early retrievals boost salience fast.
        """
        if not node_ids:
            return []
        graph = self.select_graph()
        query = """
        MATCH (n:Entity)
        WHERE n.id IN $ids
        SET n.retrieval_count = COALESCE(n.retrieval_count, 0) + 1,
            n.salience_score = 1.0 + log2(1 + COALESCE(n.retrieval_count, 0) + 1)
        RETURN n.id AS id, n.salience_score AS salience_score, n.retrieval_count AS retrieval_count
        """
        result = graph.query(query, {"ids": node_ids})
        return [
            {
                "id": row[0],
                "salience_score": row[1],
                "retrieval_count": row[2],
            }
            for row in result.result_set
        ]

    @retry_on_transient()
    def get_most_recent_entity(self, project_id: str) -> dict[str, Any] | None:
        """Return the most recently created entity in a project (for PRECEDED_BY linking)."""
        graph = self.select_graph()
        query = """
        MATCH (n:Entity {project_id: $pid})
        RETURN n
        ORDER BY COALESCE(n.occurred_at, n.created_at) DESC
        LIMIT 1
        """
        result = graph.query(query, {"pid": project_id})
        if not result.result_set:
            return None
        node = result.result_set[0][0]
        return dict(node.properties) if hasattr(node, "properties") else None

    @retry_on_transient()
    def query_timeline(
        self,
        start: str,
        end: str,
        limit: int = 20,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch entities within a time window, ordered by occurred_at.

        Falls back to created_at for entities without occurred_at.
        """
        graph = self.select_graph()
        if project_id:
            query = """
            MATCH (n:Entity)
            WHERE COALESCE(n.occurred_at, n.created_at) >= $start
              AND COALESCE(n.occurred_at, n.created_at) <= $end
              AND n.project_id = $project_id
            RETURN n
            ORDER BY COALESCE(n.occurred_at, n.created_at) ASC
            LIMIT $limit
            """
            params = {
                "start": start,
                "end": end,
                "project_id": project_id,
                "limit": limit,
            }
        else:
            query = """
            MATCH (n:Entity)
            WHERE COALESCE(n.occurred_at, n.created_at) >= $start
              AND COALESCE(n.occurred_at, n.created_at) <= $end
            RETURN n
            ORDER BY COALESCE(n.occurred_at, n.created_at) ASC
            LIMIT $limit
            """
            params = {"start": start, "end": end, "limit": limit}
        result = graph.query(query, params)
        return [row[0].properties for row in result.result_set if row]

    @retry_on_transient()
    def get_temporal_neighbors(
        self,
        entity_id: str,
        direction: str = "both",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find entities connected by temporal edges.

        Args:
            entity_id: The anchor entity ID.
            direction: 'before', 'after', or 'both'.
            limit: Max results.
        """
        graph = self.select_graph()
        temporal_types = "PRECEDED_BY|EVOLVED_FROM|SUPERSEDES|CONCURRENT_WITH"
        if direction == "before":
            query = f"""
            MATCH (n:Entity {{id: $entity_id}})<-[r:{temporal_types}]-(m:Entity)
            RETURN m
            ORDER BY COALESCE(m.occurred_at, m.created_at) DESC
            LIMIT $limit
            """
        elif direction == "after":
            query = f"""
            MATCH (n:Entity {{id: $entity_id}})-[r:{temporal_types}]->(m:Entity)
            RETURN m
            ORDER BY COALESCE(m.occurred_at, m.created_at) ASC
            LIMIT $limit
            """
        else:
            query = f"""
            MATCH (n:Entity {{id: $entity_id}})-[r:{temporal_types}]-(m:Entity)
            RETURN DISTINCT m
            ORDER BY COALESCE(m.occurred_at, m.created_at) ASC
            LIMIT $limit
            """
        result = graph.query(query, {"entity_id": entity_id, "limit": limit})
        return [row[0].properties for row in result.result_set if row]

    @retry_on_transient()
    def create_temporal_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str = "PRECEDED_BY",
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a temporal relationship between two entities.

        Args:
            from_id: Source entity ID.
            to_id: Target entity ID.
            edge_type: One of the temporal EdgeType values.
            properties: Optional edge properties.
        """
        graph = self.select_graph()
        props = properties.copy() if properties else {}
        if "created_at" not in props:
            props["created_at"] = datetime.now(UTC).isoformat()

        query = f"""
        MATCH (a:Entity {{id: $from_id}}), (b:Entity {{id: $to_id}})
        CREATE (a)-[r:{edge_type}]->(b)
        SET r = $props
        RETURN type(r) AS rel_type, a.id AS from_id, b.id AS to_id
        """
        result = graph.query(
            query,
            {"from_id": from_id, "to_id": to_id, "props": props},
        )
        if not result.result_set:
            return {"error": "One or both entities not found"}
        row = result.result_set[0]
        return {
            "rel_type": row[0],
            "from_id": row[1],
            "to_id": row[2],
        }
