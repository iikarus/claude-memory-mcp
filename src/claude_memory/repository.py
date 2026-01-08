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
        self.password = password or os.getenv("FALKORDB_PASSWORD", "claudememory2026")

        self.client = FalkorDB(
            host=self.host,
            port=self.port,
            password=self.password,
        )
        self.graph_name = "claude_memory"

    def select_graph(self):
        return self.client.select_graph(self.graph_name)

    def ensure_indices(self) -> None:
        """Create necessary indices if they don't exist."""
        graph = self.select_graph()
        query = """
        CREATE VECTOR INDEX FOR (e:Entity) ON (e.embedding)
        OPTIONS {dimension: 1024, similarityFunction: 'cosine'}
        """
        try:
            graph.query(query)
        except Exception:
            pass

    def create_node(
        self, label: str, properties: Dict[str, Any], embedding: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Creates a node with optional vector embedding."""
        graph = self.select_graph()
        props = properties.copy()

        # Build query
        # We assume label is safe (validated by caller/schema)
        # We manually construct the label part, but bind properties

        embedding_clause = ""
        params = {"props": props}

        if embedding:
            embedding_clause = "SET n.embedding = vecf32($embedding)"
            params["embedding"] = embedding

        query = f"""
        CREATE (n:{label}:Entity)
        SET n = $props
        {embedding_clause}
        RETURN n
        """

        result = graph.query(query, params)
        return result.result_set[0][0].properties

    def update_node(
        self, node_id: str, properties: Dict[str, Any], embedding: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Updates a node's properties and/or embedding."""
        graph = self.select_graph()
        props = properties.copy()

        query_parts = []
        query_parts.append("MATCH (n:Entity {id: $id})")
        query_parts.append("SET n += $props")

        params = {"id": node_id, "props": props}

        if embedding:
            query_parts.append("SET n.embedding = vecf32($embedding)")
            params["embedding"] = embedding

        query_parts.append("RETURN n")
        query = "\n".join(query_parts)

        result = graph.query(query, params)
        if not result.result_set:
            return {}
        return result.result_set[0][0].properties

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
        return result.result_set[0][0].properties

    def delete_edge(self, edge_id: str) -> bool:
        """Deletes a relationship by ID."""
        graph = self.select_graph()
        query = "MATCH ()-[r]->() WHERE r.id = $id DELETE r"
        graph.query(query, {"id": edge_id})
        return True

    def query_vector(
        self, embedding: List[float], k: int = 10, filters: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """Executes a native vector search."""
        graph = self.select_graph()

        # Construct filter clause
        where_clause = ""
        params = {"vec": embedding, "k": k}

        if filters and "project_id" in filters:
            where_clause = "WHERE ($project_id IS NULL OR node.project_id = $project_id)"
            params["project_id"] = filters["project_id"]

        query = f"""
        CALL db.idx.vector.queryNodes('Entity', 'embedding', $k, vecf32($vec))
        YIELD node, score
        {where_clause}
        RETURN node, score
        """

        try:
            return graph.query(query, params).result_set
        except Exception as e:
            # Re-raise to let service handle fallback or logging
            raise e

    def execute_cypher(self, query: str, params: Dict[str, Any] = None) -> Any:
        """Executes a raw Cypher query."""
        graph = self.select_graph()
        return graph.query(query, params or {})
