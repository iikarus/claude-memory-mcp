import logging
import os
from typing import Any, Dict, List, Optional

from falkordb import FalkorDB

logger = logging.getLogger(__name__)


class MemoryRepository:
    """
    Data Access Layer for FalkorDB.
    Handles all direct database interactions, Cypher queries, and Index management.
    """

    def __init__(
        self, host: Optional[str] = None, port: Optional[int] = None, password: Optional[str] = None
    ) -> None:
        self.host = host or os.getenv("FALKORDB_HOST", "localhost")
        self.port = port or int(os.getenv("FALKORDB_PORT", 6379))
        self.password = password or os.getenv("FALKORDB_PASSWORD")

        self.client = FalkorDB(
            host=self.host,
            port=self.port,
            password=self.password,
        )
        self.graph_name = "claude_memory"

    def select_graph(self) -> Any:
        return self.client.select_graph(self.graph_name)

    def ensure_indices(self) -> None:
        """Create necessary indices if they don't exist."""
        # No longer manages vector indices.
        # Could add index on 'id' or 'name' for speed if not implicit in Node Key.
        pass

    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a node (embedding logic moved to VectorStore)."""
        graph = self.select_graph()
        props = properties.copy()

        # Build query
        params: Dict[str, Any] = {"props": props}

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

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a node by its ID."""
        graph = self.select_graph()
        query = "MATCH (n) WHERE n.id = $id RETURN n"
        result = graph.query(query, {"id": node_id})

        if not result.result_set:
            return None

        return result.result_set[0][0].properties  # type: ignore

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
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
        self, node_id: str, soft_delete: bool = False, reason: Optional[str] = None
    ) -> bool:
        """Deletes a node (hard or soft)."""
        graph = self.select_graph()

        if soft_delete:
            query = "MATCH (n) WHERE n.id = $id SET n.deleted = true, n.deletion_reason = $reason RETURN n"
            res = graph.query(query, {"id": node_id, "reason": reason})
            return bool(res.result_set)
        else:
            query = "MATCH (n) WHERE n.id = $id DETACH DELETE n"
            graph.query(query, {"id": node_id})
            return True

    def create_edge(
        self, from_id: str, to_id: str, relation_type: str, properties: Dict[str, Any]
    ) -> Dict[str, Any]:
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

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a raw Cypher query."""
        graph = self.select_graph()
        return graph.query(query, params or {})

    def get_subgraph(self, start_node_ids: List[str], depth: int = 1) -> Dict[str, Any]:
        """Retrieves a subgraph of connected nodes up to 'depth' hops from start nodes."""
        if not start_node_ids:
            return {"nodes": [], "edges": []}

        graph = self.select_graph()

        # Optimization: If depth is 0, just fetch nodes directly (Fixes UNWIND bug on empty paths)
        if depth == 0:
            query_nodes = """
            MATCH (n:Entity) WHERE n.id IN $ids
            RETURN collect(distinct {id: n.id, labels: labels(n), properties: properties(n)}) as nodes
            """
            res_nodes = graph.query(query_nodes, {"ids": start_node_ids})
            if res_nodes.result_set:
                # Extract inner dict properties
                return {"nodes": [n["properties"] for n in res_nodes.result_set[0][0]], "edges": []}
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
        # But larger depth might explode. 'limit' helps? user implementation plan didn't specify limit but implicit safety needed.
        # Let's use simple match for V1.

        query = f"""
        MATCH path = (root:Entity)-[*0..{depth}]-(neighbor)
        WHERE root.id IN $ids
        RETURN path
        """

        # Safer Query returning distinct nodes and edges as Maps for consistent parsing
        query = f"""
        MATCH path = (root:Entity)-[*0..{depth}]-(neighbor)
        WHERE root.id IN $ids
        UNWIND relationships(path) as r
        WITH distinct r, startNode(r) as s, endNode(r) as e
        RETURN collect(distinct {{id: r.id, source: s.id, target: e.id, type: type(r), properties: properties(r)}}) as edges,
               collect(distinct {{id: s.id, labels: labels(s), properties: properties(s)}}) + collect(distinct {{id: e.id, labels: labels(e), properties: properties(e)}}) as nodes
        """

        result = graph.query(query, {"ids": start_node_ids})

        # Now we parse the JSON-like maps returned
        if not result.result_set:
            # It might be empty if 0 hops and no edges?
            # Fallback for isolated nodes (depth 0)
            query_nodes = """
             MATCH (n:Entity) WHERE n.id IN $ids
             RETURN collect(distinct {id: n.id, labels: labels(n), properties: properties(n)}) as nodes
             """
            res_nodes = graph.query(query_nodes, {"ids": start_node_ids})
            if res_nodes.result_set:
                return {"nodes": [n["properties"] for n in res_nodes.result_set[0][0]], "edges": []}
            return {"nodes": [], "edges": []}

        row = result.result_set[0]
        edges_data = row[0]
        nodes_data = row[1]

        # Deduplicate nodes by ID (Cypher set might not be perfect with maps)
        unique_nodes = {n["id"]: n["properties"] for n in nodes_data}
        unique_edges = {e["id"]: e for e in edges_data}  # e has source/target/type merged in

        return {"nodes": list(unique_nodes.values()), "edges": list(unique_edges.values())}

    def get_all_nodes(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieves all entity nodes with their embeddings for clustering."""
        graph = self.select_graph()
        query = """
        MATCH (n:Entity)
        WHERE n.embedding IS NOT NULL
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
