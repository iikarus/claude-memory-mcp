"""FalkorDB data access layer — Cypher queries, node/edge CRUD, and index management."""

import logging
import os
import time
from typing import Any

from falkordb import FalkorDB

from claude_memory.repository_queries import RepositoryQueryMixin
from claude_memory.repository_traversal import RepositoryTraversalMixin
from claude_memory.retry import retry_on_transient

logger = logging.getLogger(__name__)

_CONSTRUCTOR_MAX_RETRIES = 3
_CONSTRUCTOR_BASE_DELAY = 1.0


class MemoryRepository(RepositoryQueryMixin, RepositoryTraversalMixin):
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

        self.client = self._connect_with_retry()
        self.graph_name = "claude_memory"

    def _connect_with_retry(self) -> FalkorDB:
        """Attempt to connect to FalkorDB with retry on transient failures."""
        for attempt in range(_CONSTRUCTOR_MAX_RETRIES):
            try:
                return FalkorDB(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                )
            except (ConnectionError, TimeoutError, OSError) as exc:
                if attempt == _CONSTRUCTOR_MAX_RETRIES - 1:
                    logger.error(
                        "FalkorDB connection failed after %d attempts: %s",
                        _CONSTRUCTOR_MAX_RETRIES,
                        exc,
                    )
                    raise
                delay = _CONSTRUCTOR_BASE_DELAY * (2**attempt)
                logger.warning(
                    "FalkorDB connect retry %d/%d in %.1fs — %s",
                    attempt + 1,
                    _CONSTRUCTOR_MAX_RETRIES,
                    delay,
                    exc,
                )
                time.sleep(delay)
        raise ConnectionError("FalkorDB connection exhausted retries")  # pragma: no cover

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
