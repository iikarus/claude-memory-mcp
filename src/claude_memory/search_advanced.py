"""Advanced search operations — spreading activation and hologram.

Extracted from search.py to keep each file under 300 lines.
Mixed into SearchMixin at runtime.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .schema import SearchResult

logger = logging.getLogger(__name__)


class SearchAdvancedMixin:
    """Associative search and hologram retrieval — mixed into SearchMixin.

    Expects the host class to provide: ``embedder``, ``vector_store``,
    ``activation_engine``, ``repo``, ``context_manager``,
    ``_fire_salience_update()``, and ``search()``.
    """

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
        try:
            vec = self.embedder.encode(query)  # type: ignore[attr-defined]
            search_filter: dict[str, Any] | None = None
            if project_id:
                search_filter = {"project_id": project_id}

            vector_results = await self.vector_store.search(  # type: ignore[attr-defined]
                vector=vec, limit=limit, filter=search_filter
            )
            if not vector_results:
                return []

            seed_ids = [item["_id"] for item in vector_results]
            vector_scores = {item["_id"]: item["_score"] for item in vector_results}

            # 2. Spreading activation
            activation_map = self.activation_engine.activate(seed_ids)  # type: ignore[attr-defined]
            activation_map = self.activation_engine.spread(  # type: ignore[attr-defined]
                activation_map, decay=decay, max_hops=max_hops
            )

            # 3. Gather all candidate IDs (seeds + spread targets)
            all_ids = list(set(seed_ids) | set(activation_map.keys()))
            graph_data = self.repo.get_subgraph(all_ids, depth=0)  # type: ignore[attr-defined]
            nodes_map = {n["id"]: n for n in graph_data["nodes"]}

            # Fire-and-forget salience update for associative search too
            result_ids = list(nodes_map.keys())
            self._fire_salience_update(result_ids)  # type: ignore[attr-defined]

            # Build salience map from graph properties (pre-update values)
            salience_map = {
                nid: props.get("salience_score", 0.0) for nid, props in nodes_map.items()
            }

            # 4. Composite ranking
            candidates = list(nodes_map.values())
            ranked = self.activation_engine.rank(  # type: ignore[attr-defined]
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
        except (ConnectionError, TimeoutError, OSError, ValueError):
            logger.error("search_associative failed for query=%r", query, exc_info=True)
            return []

    async def get_hologram(
        self, query: str, depth: int = 1, max_tokens: int = 8000
    ) -> dict[str, Any]:
        """Retrieves a 'Hologram' (connected subgraph) relevant to the query.

        Algorithm:
        1. Search for top entities (Anchors).
        2. Expand outward from Anchors by 'depth'.
        3. Return the consolidated subgraph.
        """
        logger.info("Generating Hologram for: %s", query)

        # 1. Get Anchors
        anchors = await self.search(query, limit=5)  # type: ignore[attr-defined]

        if not anchors:
            return {"nodes": [], "edges": []}

        anchor_ids = [a.id for a in anchors]

        # 2. Expand Subgraph
        hologram = self.repo.get_subgraph(anchor_ids, depth)  # type: ignore[attr-defined]

        # 3. Assemble and Optimize
        raw_nodes = hologram.get("nodes", [])
        raw_edges = hologram.get("edges", [])

        # Sanitization: Strip embeddings to prevent context flood
        for n in raw_nodes:
            if isinstance(n, dict):
                n.pop("embedding", None)

        # Optimize using Token Budget
        optimized_nodes = self.context_manager.optimize(  # type: ignore[attr-defined]
            raw_nodes, max_tokens=max_tokens
        )

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
