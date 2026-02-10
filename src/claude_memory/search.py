"""Search operations for the Exocortex memory system.

Provides vector search, spreading-activation, path traversal, hologram, and
point-in-time queries.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .activation import ActivationEngine
    from .context_manager import ContextManager
    from .interfaces import Embedder, VectorStore
    from .repository import MemoryRepository
    from .router import QueryRouter
    from .schema import SearchResult

logger = logging.getLogger(__name__)


class SearchMixin:
    """Search / traversal / hologram methods — mixed into MemoryService."""

    repo: "MemoryRepository"
    embedder: "Embedder"
    vector_store: "VectorStore"
    router: "QueryRouter"
    activation_engine: "ActivationEngine"
    context_manager: "ContextManager"

    # Provided by CrudMixin (also mixed into MemoryService)
    def _fire_salience_update(self, ids: list[str]) -> None: ...

    async def get_neighbors(
        self, entity_id: str, depth: int = 1, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Retrieve entities connected within a given hop depth."""
        depth = max(depth, 1)
        query = f"""
        MATCH (n)-[*1..{depth}]-(m)
        WHERE n.id = $entity_id
        RETURN distinct m
        SKIP $offset
        LIMIT $limit
        """
        res = self.repo.execute_cypher(
            query, {"entity_id": entity_id, "limit": limit, "offset": offset}
        )
        nodes = [row[0].properties for row in res.result_set if row]
        for n in nodes:
            n.pop("embedding", None)
        return nodes

    async def traverse_path(self, from_id: str, to_id: str) -> list[dict[str, Any]]:
        """Find the shortest path between two entities."""
        query = """
        MATCH p = shortestPath((a)-[*]-(b))
        WHERE a.id = $start AND b.id = $end
        RETURN p
        """
        res = self.repo.execute_cypher(query, {"start": from_id, "end": to_id})
        path_data = []
        if res.result_set and res.result_set[0]:
            path_obj = res.result_set[0][0]
            if hasattr(path_obj, "nodes"):
                for node in path_obj.nodes:
                    props = node.properties
                    props.pop("embedding", None)
                    path_data.append(props)
        return path_data

    async def find_cross_domain_patterns(
        self, entity_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Find nodes in different projects connected to this entity."""
        query = """
        MATCH (n:Entity {id: $entity_id})
        MATCH (n)-[*1..3]-(m:Entity)
        WHERE m.project_id <> n.project_id
        RETURN distinct m
        LIMIT $limit
        """
        res = self.repo.execute_cypher(query, {"entity_id": entity_id, "limit": limit})
        nodes = [row[0].properties for row in res.result_set if row]
        for n in nodes:
            n.pop("embedding", None)
        return nodes

    async def get_evolution(self, entity_id: str) -> list[dict[str, Any]]:
        """Retrieve the evolution (history/observations) of an entity."""
        query = """
        MATCH (e:Entity {id: $entity_id})-[:HAS_OBSERVATION]->(o)
        RETURN o
        ORDER BY o.created_at DESC
        """
        res = self.repo.execute_cypher(query, {"entity_id": entity_id})
        nodes = [row[0].properties for row in res.result_set if row]
        for n in nodes:
            n.pop("embedding", None)
        return nodes

    async def point_in_time_query(self, query_text: str, as_of: str) -> list[dict[str, Any]]:
        """Execute a search considering only knowledge known before `as_of`."""
        vec = self.embedder.encode(query_text)

        # Use VectorStore with time filter
        vector_results = await self.vector_store.search(
            vector=vec, limit=10, filter={"created_at_lt": as_of}
        )

        if not vector_results:
            return []

        # Hydrate from Graph
        ids = [item["_id"] for item in vector_results]
        graph_data = self.repo.get_subgraph(ids, depth=0)

        # Flatten
        nodes = list(graph_data["nodes"])
        for n in nodes:
            n.pop("embedding", None)
        return nodes

    async def search(  # noqa: PLR0913
        self,
        query: str,
        limit: int = 5,
        project_id: str | None = None,
        offset: int = 0,
        mmr: bool = False,
        strategy: str | None = None,
    ) -> list["SearchResult"]:
        """Search for entities, optionally routing via QueryRouter.

        When ``strategy`` is provided, dispatches via :class:`QueryRouter`:
        - ``'auto'`` — auto-classify intent from the query text
        - ``'semantic'`` / ``'associative'`` / ``'temporal'`` / ``'relational'``
        When ``strategy`` is None, uses direct vector search (default).
        """
        from .router import QueryIntent  # noqa: PLC0415
        from .schema import SearchResult  # noqa: PLC0415

        if not query:
            return []

        # Route through QueryRouter if strategy is specified
        if strategy is not None:
            intent = None if strategy == "auto" else QueryIntent(strategy)
            results = await self.router.route(
                query,
                self,  # type: ignore[arg-type]  # self is MemoryService at runtime
                intent=intent,
                limit=limit,
                project_id=project_id,
            )
            # router.route may return dicts (temporal/relational) or SearchResults
            if results and isinstance(results[0], dict):
                return [
                    SearchResult(
                        id=r.get("id", ""),
                        name=r.get("name", "Unknown"),
                        node_type=r.get("node_type", "Entity"),
                        project_id=r.get("project_id", "unknown"),
                        content=r.get("description", ""),
                        score=0.0,
                        distance=0.0,
                    )
                    for r in results
                ]
            return results

        # 1. Embed Query
        vec = self.embedder.encode(query)

        # 2. Search Qdrant (Vector Engine)
        search_filter: dict[str, Any] | None = None
        if project_id:
            search_filter = {"project_id": project_id}

        if mmr:
            vector_results = await self.vector_store.search_mmr(
                vector=vec, limit=limit, filter=search_filter
            )
        else:
            vector_results = await self.vector_store.search(
                vector=vec, limit=limit, filter=search_filter, offset=offset
            )

        if not vector_results:
            return []

        # 3. Hydrate from Graph
        # We have IDs, fetch full nodes.
        ids = [item["_id"] for item in vector_results]

        # We can use get_subgraph with depth 0 to get nodes
        graph_data = self.repo.get_subgraph(ids, depth=0)
        nodes_map = {n["id"]: n for n in graph_data["nodes"]}

        # 4. Fire-and-forget salience update (non-blocking)
        self._fire_salience_update(ids)
        salience_map = {nid: props.get("salience_score", 0.0) for nid, props in nodes_map.items()}

        results = []
        for v_res in vector_results:
            node_id = v_res["_id"]
            if node_id in nodes_map:
                node_props = nodes_map[node_id]
                results.append(
                    SearchResult(
                        id=node_id,
                        name=node_props.get("name", "Unknown"),
                        node_type=node_props.get("node_type", "Entity"),
                        project_id=node_props.get("project_id", "unknown"),
                        content=node_props.get("description", ""),
                        score=v_res["_score"],
                        distance=1.0 - v_res["_score"],
                        salience_score=salience_map.get(
                            node_id,
                            node_props.get("salience_score", 0.0),
                        ),
                    )
                )
        return results

    async def search_associative(  # noqa: PLR0913
        self,
        query: str,
        limit: int = 10,
        project_id: str | None = None,
        *,
        decay: float = 0.6,
        max_hops: int = 3,
        w_sim: float | None = None,
        w_act: float | None = None,
        w_sal: float | None = None,
        w_rec: float | None = None,
    ) -> list["SearchResult"]:
        """Spreading-activation search: vector → graph spread → composite rank.

        1. Vector search to find initial seed nodes.
        2. Activate seeds and spread energy through the graph.
        3. Hydrate candidate entities from graph.
        4. Composite rank with configurable weights (env var / per-query).
        """
        from .schema import SearchResult  # noqa: PLC0415

        if not query:
            return []

        # 1. Vector search for seed nodes
        vec = self.embedder.encode(query)
        search_filter: dict[str, Any] | None = None
        if project_id:
            search_filter = {"project_id": project_id}

        vector_results = await self.vector_store.search(
            vector=vec, limit=limit, filter=search_filter
        )
        if not vector_results:
            return []

        seed_ids = [item["_id"] for item in vector_results]
        vector_scores = {item["_id"]: item["_score"] for item in vector_results}

        # 2. Spreading activation
        activation_map = self.activation_engine.activate(seed_ids)
        activation_map = self.activation_engine.spread(
            activation_map, decay=decay, max_hops=max_hops
        )

        # 3. Gather all candidate IDs (seeds + spread targets)
        all_ids = list(set(seed_ids) | set(activation_map.keys()))
        graph_data = self.repo.get_subgraph(all_ids, depth=0)
        nodes_map = {n["id"]: n for n in graph_data["nodes"]}

        # Fire-and-forget salience update for associative search too
        result_ids = list(nodes_map.keys())
        self._fire_salience_update(result_ids)

        # Build salience map from graph properties (pre-update values)
        salience_map = {nid: props.get("salience_score", 0.0) for nid, props in nodes_map.items()}

        # 4. Composite ranking
        candidates = list(nodes_map.values())
        ranked = self.activation_engine.rank(
            candidates,
            vector_scores,
            activation_map,
            salience_map,
            w_sim=w_sim,
            w_act=w_act,
            w_sal=w_sal,
            w_rec=w_rec,
        )

        # 5. Convert to SearchResult
        results = []
        for entity in ranked[:limit]:
            eid = entity.get("id", "")
            results.append(
                SearchResult(
                    id=eid,
                    name=entity.get("name", "Unknown"),
                    node_type=entity.get("node_type", "Entity"),
                    project_id=entity.get("project_id", "unknown"),
                    content=entity.get("description", ""),
                    score=entity.get("composite_score", 0.0),
                    distance=1.0 - vector_scores.get(eid, 0.0),
                    salience_score=salience_map.get(eid, 0.0),
                )
            )
        return results

    async def get_hologram(
        self, query: str, depth: int = 1, max_tokens: int = 8000
    ) -> dict[str, Any]:
        """
        Retrieves a 'Hologram' (connected subgraph) relevant to the query.

        Algorithm:
        1. Search for top entities (Anchors).
        2. Expand outward from Anchors by 'depth'.
        3. Return the consolidated subgraph.
        """
        logger.info(f"Generating Hologram for: {query}")

        # 1. Get Anchors
        anchors = await self.search(query, limit=5)

        if not anchors:
            return {"nodes": [], "edges": []}

        anchor_ids = [a.id for a in anchors]

        # 2. Expand Subgraph
        hologram = self.repo.get_subgraph(anchor_ids, depth)

        # 3. Assemble and Optimize
        raw_nodes = hologram.get("nodes", [])
        raw_edges = hologram.get("edges", [])

        # Sanitization: Strip embeddings to prevent context flood
        for n in raw_nodes:
            if isinstance(n, dict):
                n.pop("embedding", None)

        # Optimize using Token Budget
        optimized_nodes = self.context_manager.optimize(raw_nodes, max_tokens=max_tokens)

        # Filter edges: only keep edges where both nodes are in the optimized set
        final_node_ids = {n["id"] for n in optimized_nodes}

        optimized_edges = [
            e for e in raw_edges if e["source"] in final_node_ids and e["target"] in final_node_ids
        ]

        return {
            "query": query,
            "anchors": [a.model_dump() for a in anchors],
            "nodes": optimized_nodes,
            "edges": optimized_edges,
            "stats": {
                "total_nodes": len(optimized_nodes),
                "total_edges": len(optimized_edges),
                "original_node_count": len(raw_nodes),
                "pruned": len(raw_nodes) > len(optimized_nodes),
            },
        }
