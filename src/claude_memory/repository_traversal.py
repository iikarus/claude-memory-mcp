"""Mixin for graph traversal and analytics queries."""

import logging
from typing import Any

from claude_memory.retry import retry_on_transient

logger = logging.getLogger(__name__)


class RepositoryTraversalMixin:
    """Methods for traversing the graph and retrieving aggregate data."""

    def select_graph(self) -> Any:
        """Protocol method to be implemented by the main Repository class."""
        raise NotImplementedError

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
        Uses log(x)/log(2) since FalkorDB doesn't support log2().
        This gives diminishing returns — early retrievals boost salience fast.
        """
        if not node_ids:
            return []
        graph = self.select_graph()
        query = """
        MATCH (n:Entity)
        WHERE n.id IN $ids
        SET n.retrieval_count = COALESCE(n.retrieval_count, 0) + 1,
            n.salience_score = 1.0 + log(1 + COALESCE(n.retrieval_count, 0) + 1) / log(2)
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
