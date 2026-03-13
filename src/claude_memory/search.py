"""Search operations for the Claude Memory system.

Provides vector search, spreading-activation, path traversal, hologram, and
point-in-time queries.  ADR-007 hybrid search unification.
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from claude_memory.merge import MergedResult, rrf_merge
from claude_memory.search_advanced import SearchAdvancedMixin

if TYPE_CHECKING:  # pragma: no cover
    from .activation import ActivationEngine
    from .context_manager import ContextManager
    from .interfaces import Embedder, VectorStore
    from .repository import MemoryRepository
    from .router import QueryRouter
    from .schema import SearchResult

logger = logging.getLogger(__name__)


class SearchMixin(SearchAdvancedMixin):
    """Search / traversal methods — mixed into MemoryService.

    Inherits ``search_associative`` and ``get_hologram`` from SearchAdvancedMixin.
    """

    repo: "MemoryRepository"
    embedder: "Embedder"
    vector_store: "VectorStore"
    router: "QueryRouter"
    activation_engine: "ActivationEngine"
    context_manager: "ContextManager"

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
        """Find the shortest path between two entities.

        FalkorDB requires directed shortestPath traversals, so we try
        both directions (forward and reverse) and return whichever succeeds.
        """

        def _extract_path(res: Any) -> list[dict[str, Any]]:
            """Extract node properties from a FalkorDB shortestPath result."""
            path_data: list[dict[str, Any]] = []
            if res.result_set and res.result_set[0]:
                path_obj = res.result_set[0][0]
                if hasattr(path_obj, "nodes"):
                    nodes = path_obj.nodes() if callable(path_obj.nodes) else path_obj.nodes
                    for node in nodes:
                        props = node.properties
                        props.pop("embedding", None)
                        path_data.append(props)
            return path_data

        params = {"start": from_id, "end": to_id}

        # Try forward direction first
        fwd_query = """
        MATCH (a:Entity {id: $start}), (b:Entity {id: $end})
        WITH shortestPath((a)-[*..10]->(b)) AS p
        RETURN p
        """
        try:
            res = self.repo.execute_cypher(fwd_query, params)
            path_data = _extract_path(res)
            if path_data:
                return path_data
        except Exception:  # noqa: S110  # nosec B110
            # Forward traversal failed (e.g. no directed path), try reverse
            pass

        # Try reverse direction
        rev_query = """
        MATCH (a:Entity {id: $start}), (b:Entity {id: $end})
        WITH shortestPath((b)-[*..10]->(a)) AS p
        RETURN p
        """
        res = self.repo.execute_cypher(rev_query, params)
        path_data = _extract_path(res)
        if path_data:
            path_data.reverse()
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

    # ── Main search entry point (ADR-007 hybrid pipeline) ────────────

    async def search(  # noqa: PLR0913
        self,
        query: str,
        limit: int = 5,
        project_id: str | None = None,
        offset: int = 0,
        mmr: bool = False,
        strategy: str | None = None,
        deep: bool = False,
        temporal_window_days: int = 7,
    ) -> list["SearchResult"]:
        """Search for entities using the hybrid pipeline (ADR-007).

        Default path (``strategy=None``): vector search + intent-based graph
        enrichment + RRF merge.  Explicit strategies dispatch directly.

        ``strategy='auto'`` is deprecated — logs a warning and falls through
        to the hybrid default.
        """
        if not query:
            return []

        try:
            # ── Handle explicit strategies (direct dispatch) ──
            if strategy is not None:
                if strategy == "auto":
                    logger.warning("strategy='auto' is deprecated; using hybrid default")
                    strategy = None  # fall through to hybrid
                else:
                    return await self._direct_strategy_search(
                        query, strategy, limit, project_id, temporal_window_days
                    )

            # ── HYBRID DEFAULT PATH ──

            # Step 1: Vector search (always)
            vector_results = await self._execute_vector_search(
                query, limit, project_id, offset, mmr
            )

            # Step 2: Intent classification (sequential — no asyncio.gather)
            from .router import QueryIntent  # noqa: PLC0415

            detected_intent = self.router.classify(query)

            # Step 3: Graph enrichment (based on intent)
            graph_results: list[dict[str, Any]] = []
            temporal_exhausted = False

            if detected_intent == QueryIntent.TEMPORAL:
                graph_results, temporal_exhausted = await self._temporal_enrichment(
                    query, limit, project_id, temporal_window_days
                )
            elif detected_intent == QueryIntent.RELATIONAL:
                graph_results = await self._relational_enrichment(query)
            elif detected_intent == QueryIntent.ASSOCIATIVE:
                graph_results = await self._associative_enrichment(
                    query, vector_results, limit, project_id
                )
            # SEMANTIC intent → no graph enrichment needed

            # Step 4: Merge
            if graph_results:
                merged = rrf_merge(vector_results, graph_results, k=60, limit=limit)
            else:
                # Vector-only: build trivial merged results
                merged = rrf_merge(vector_results, [], k=60, limit=limit)

            # Step 5: Hydrate
            search_results = await self._hydrate_merged_results(
                merged, detected_intent, deep, vector_results
            )

            # Store temporal exhaustion info on the instance for server layer
            self._last_temporal_exhausted = temporal_exhausted
            self._last_temporal_window_days = temporal_window_days
            self._last_temporal_result_count = (
                len(graph_results) if (detected_intent == QueryIntent.TEMPORAL) else 0
            )
            self._last_detected_intent = detected_intent

            return search_results
        except (ConnectionError, TimeoutError, OSError, ValueError):
            logger.error("search failed for query=%r", query, exc_info=True)
            return []

    # ── Explicit strategy dispatch (ADR-007 §8) ─────────────────────

    async def _direct_strategy_search(
        self,
        query: str,
        strategy: str,
        limit: int,
        project_id: str | None,
        temporal_window_days: int,
    ) -> list["SearchResult"]:
        """Dispatch to a specific strategy, with vector score attachment.

        Replaces the old ``_route_strategy_search``.  For graph-only
        strategies (temporal/relational), attaches real vector scores
        so ``score`` is never misleadingly 0.0.
        """
        from .router import QueryIntent  # noqa: PLC0415
        from .schema import SearchResult  # noqa: PLC0415

        intent = QueryIntent(strategy)
        results = await self.router.route(
            query,
            self,  # type: ignore[arg-type]
            intent=intent,
            limit=limit,
            project_id=project_id,
            temporal_window_days=temporal_window_days,
        )

        # Convert dicts to SearchResult if needed (temporal/relational return dicts)
        if results and isinstance(results[0], dict):
            results = [
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

        # Fix the score-0 problem for explicit graph strategies
        if intent in (QueryIntent.TEMPORAL, QueryIntent.RELATIONAL):
            results = await self._attach_vector_scores(query, results)

        # Tag all results with their retrieval strategy
        for r in results:
            if isinstance(r, SearchResult):
                r.retrieval_strategy = strategy

        return results

    # ── Graph enrichment helpers ─────────────────────────────────────

    async def _temporal_enrichment(
        self,
        query: str,
        limit: int,
        project_id: str | None,
        temporal_window_days: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Run temporal graph query and return (results, exhausted)."""
        from .schema import TemporalQueryParams  # noqa: PLC0415

        now = datetime.now(UTC)
        params = TemporalQueryParams(
            start=now - timedelta(days=temporal_window_days),
            end=now,
            limit=limit,
            project_id=project_id,
        )
        results = await self.query_timeline(params)  # type: ignore[attr-defined]
        exhausted = len(results) < limit
        return results, exhausted

    async def _relational_enrichment(self, query: str) -> list[dict[str, Any]]:
        """Extract entity refs from query and traverse graph paths."""
        import re  # noqa: PLC0415

        quoted = re.findall(r'"([^"]+)"', query)
        if len(quoted) >= 2:  # noqa: PLR2004
            path = await self.traverse_path(quoted[0], quoted[1])
            # Convert path nodes to dict format with id keys
            return [{"id": n.get("id", ""), **n} for n in path if isinstance(n, dict)]
        return []

    async def _associative_enrichment(
        self,
        query: str,
        vector_results: list[dict[str, Any]],
        limit: int,
        project_id: str | None,
    ) -> list[dict[str, Any]]:
        """Run spreading activation using Step 1's vector results as seeds.

        Does NOT re-search Qdrant — avoids the double-dip that calling
        ``search_associative()`` directly would cause.
        """
        if not vector_results:
            return []

        seed_ids = [vr["_id"] for vr in vector_results]
        activation_map = self.activation_engine.activate(seed_ids)
        spread_map = self.activation_engine.spread(activation_map, decay=0.6, max_hops=3)

        # Gather all activated entity IDs
        all_ids = list(set(seed_ids) | set(spread_map.keys()))
        graph_data = self.repo.get_subgraph(all_ids, depth=0)

        return [
            {"id": n.get("id", ""), **n}
            for n in graph_data.get("nodes", [])
            if isinstance(n, dict) and n.get("id")
        ][:limit]

    # ── Vector score attachment (ADR-007 §8) ─────────────────────────

    async def _attach_vector_scores(
        self,
        query: str,
        results: list["SearchResult"],
    ) -> list["SearchResult"]:
        """Batch vector lookup by entity ID to attach real scores.

        Uses ``retrieve_by_ids`` for direct point retrieval rather than
        re-running a similarity search (which could silently miss entities).
        """
        if not results:
            return results

        try:
            vec = self.embedder.encode(query)
            entity_ids = [r.id for r in results]

            # Use batch point retrieval if available, fallback to search
            if hasattr(self.vector_store, "retrieve_by_ids"):
                score_map = await self.vector_store.retrieve_by_ids(
                    ids=entity_ids, query_vector=vec
                )
            else:
                # Fallback for non-Qdrant stores
                vector_hits = await self.vector_store.search(vector=vec, limit=len(results) * 2)
                score_map = {vh["_id"]: vh["_score"] for vh in vector_hits}

            for r in results:
                if r.id in score_map:
                    r.score = score_map[r.id]
                    r.distance = 1.0 - score_map[r.id]
                    r.vector_score = score_map[r.id]
                else:
                    # Entity genuinely has no vector embedding
                    r.vector_score = None
        except (ConnectionError, TimeoutError, OSError, ValueError):
            logger.warning("_attach_vector_scores failed, scores remain 0.0", exc_info=True)

        return results

    # ── Hydration & recency ──────────────────────────────────────────

    async def _hydrate_merged_results(
        self,
        merged: list["MergedResult"],
        detected_intent: Any,
        deep: bool,
        vector_results: list[dict[str, Any]],
    ) -> list["SearchResult"]:
        """Build SearchResult objects from MergedResult entries."""
        from .router import QueryIntent  # noqa: PLC0415
        from .schema import SearchResult  # noqa: PLC0415

        if not merged:
            return []

        ids = [m.entity_id for m in merged]
        graph_depth = 1 if deep else 0
        graph_data = self.repo.get_subgraph(ids, depth=graph_depth)
        nodes_map = {n["id"]: n for n in graph_data["nodes"]}

        # Fire-and-forget salience update
        self._fire_salience_update(ids)  # type: ignore[attr-defined]
        salience_map = {nid: props.get("salience_score", 0.0) for nid, props in nodes_map.items()}

        results: list[SearchResult] = []
        for m in merged:
            node_props = nodes_map.get(m.entity_id)
            if not node_props:
                continue

            observations, relationships = self._deep_hydrate_node(m.entity_id, graph_data, deep)

            # Determine retrieval strategy label
            if len(m.retrieval_sources) > 1:
                strategy = "hybrid"
            elif "vector" in m.retrieval_sources:
                strategy = "semantic"
            else:
                strategy = (
                    detected_intent.value
                    if isinstance(detected_intent, QueryIntent)
                    else "semantic"
                )

            # Use vector score when available, otherwise RRF score
            score = m.vector_score if m.vector_score is not None else m.rrf_score
            distance = 1.0 - score if score > 0 else 0.0

            results.append(
                SearchResult(
                    id=m.entity_id,
                    name=node_props.get("name", "Unknown"),
                    node_type=node_props.get("node_type", "Entity"),
                    project_id=node_props.get("project_id", "unknown"),
                    content=node_props.get("description", ""),
                    score=score,
                    distance=distance,
                    salience_score=salience_map.get(
                        m.entity_id,
                        node_props.get("salience_score", 0.0),
                    ),
                    observations=observations,
                    relationships=relationships,
                    retrieval_strategy=strategy,
                    vector_score=m.vector_score,
                    path_distance=m.graph_metadata.get("path_distance"),
                    activation_score=m.graph_metadata.get("composite_score", 0.0),
                )
            )
            # Compute recency from graph timestamp while we have node_props
            results[-1].recency_score = self._compute_recency(
                results[-1], occurred_at=node_props.get("occurred_at")
            )
        return results

    @staticmethod
    def _compute_recency(
        result: "SearchResult",
        occurred_at: str | None = None,
    ) -> float:
        """Compute 0-1 exponential decay recency score.

        Uses ``RECENCY_HALF_LIFE_DAYS`` env var (default 7).
        Formula: ``2 ** (-age_days / half_life)``

        Args:
            result: SearchResult to score.
            occurred_at: ISO 8601 timestamp string from graph node.
                If None, returns the existing ``recency_score``.
        """
        if occurred_at is None:
            return result.recency_score

        half_life = float(os.getenv("RECENCY_HALF_LIFE_DAYS", "7"))

        try:
            ts = datetime.fromisoformat(occurred_at)
            # Ensure timezone-aware comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - ts).total_seconds() / 86400.0
            if age_days < 0:
                return 1.0  # future timestamps → max recency
            return float(2.0 ** (-age_days / half_life))
        except (ValueError, TypeError):
            logger.debug("Invalid occurred_at '%s', falling back to default", occurred_at)
            return result.recency_score

    # ── Existing helpers (unchanged) ─────────────────────────────────

    async def _execute_vector_search(
        self,
        query: str,
        limit: int,
        project_id: str | None,
        offset: int,
        mmr: bool,
    ) -> list[dict[str, Any]]:
        """Embed query and search Qdrant (standard or MMR)."""
        vec = self.embedder.encode(query)

        search_filter: dict[str, Any] | None = None
        if project_id:
            search_filter = {"project_id": project_id}

        if mmr:
            return await self.vector_store.search_mmr(vector=vec, limit=limit, filter=search_filter)
        return await self.vector_store.search(
            vector=vec, limit=limit, filter=search_filter, offset=offset
        )

    def _hydrate_search_results(
        self,
        vector_results: list[dict[str, Any]],
        deep: bool,
    ) -> list["SearchResult"]:
        """Hydrate vector hits from graph and build SearchResult list."""
        from .schema import SearchResult  # noqa: PLC0415

        ids = [item["_id"] for item in vector_results]

        graph_depth = 1 if deep else 0
        graph_data = self.repo.get_subgraph(ids, depth=graph_depth)
        nodes_map = {n["id"]: n for n in graph_data["nodes"]}

        # Fire-and-forget salience update (non-blocking)
        self._fire_salience_update(ids)  # type: ignore[attr-defined]
        salience_map = {nid: props.get("salience_score", 0.0) for nid, props in nodes_map.items()}

        results = []
        for v_res in vector_results:
            node_id = v_res["_id"]
            if node_id not in nodes_map:
                continue

            node_props = nodes_map[node_id]
            observations, relationships = self._deep_hydrate_node(node_id, graph_data, deep)

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
                    observations=observations,
                    relationships=relationships,
                )
            )
        return results

    def _deep_hydrate_node(
        self,
        node_id: str,
        graph_data: dict[str, Any],
        deep: bool,
    ) -> tuple[list[str], list[dict[str, str]]]:
        """Fetch observations and relationships for a node when deep=True."""
        if not deep:
            return [], []

        obs_query = (
            "MATCH (e:Entity {id: $eid})-[:HAS_OBSERVATION]->(o) "
            "RETURN o.content ORDER BY o.created_at ASC"
        )
        obs_res = self.repo.execute_cypher(obs_query, {"eid": node_id})
        observations = [row[0] for row in obs_res.result_set if row[0]]
        relationships = [
            e for e in graph_data["edges"] if e.get("src") == node_id or e.get("dst") == node_id
        ]
        return observations, relationships
