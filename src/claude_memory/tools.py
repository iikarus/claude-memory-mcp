"""Core business logic for the Exocortex memory system (CRUD, search, analysis)."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from claude_memory.activation import ActivationEngine
from claude_memory.context_manager import ContextManager
from claude_memory.interfaces import Embedder
from claude_memory.router import QueryIntent, QueryRouter

from .lock_manager import LockManager
from .ontology import OntologyManager
from .repository import MemoryRepository
from .schema import (
    BottleQueryParams,
    BreakthroughParams,
    EntityCommitReceipt,
    EntityCreateParams,
    EntityDeleteParams,
    EntityUpdateParams,
    GapDetectionParams,
    ObservationParams,
    RelationshipCreateParams,
    RelationshipDeleteParams,
    SearchResult,
    SessionEndParams,
    SessionStartParams,
    TemporalQueryParams,
)
from .vector_store import QdrantVectorStore, VectorStore

# Configure logging
logger = logging.getLogger(__name__)


class MemoryService:
    """Orchestrates graph, vector, and ontology operations for memory management."""

    def __init__(
        self,
        embedding_service: Embedder,
        vector_store: VectorStore | None = None,
        host: str | None = None,
        port: int | None = None,
        password: str | None = None,
    ) -> None:
        """Wire up repository, embedder, vector store, ontology, and lock manager."""
        self.repo = MemoryRepository(host, port, password)
        # self.repo.ensure_indices() # Deprecated: Repository no longer manages vectors
        self.embedder = embedding_service
        self.vector_store = vector_store or QdrantVectorStore()

        # Core Components
        self.ontology = OntologyManager()
        self.context_manager = ContextManager()
        # Share connection config
        self.lock_manager = LockManager(host, port)
        # Strategy objects (stateless — cached, not per-call)
        self.router = QueryRouter()
        self.activation_engine = ActivationEngine(repo=self.repo)
        # Background tasks for fire-and-forget operations
        self._background_tasks: set[asyncio.Task[None]] = set()

    def _fire_salience_update(self, ids: list[str]) -> None:
        """Fire-and-forget salience increment so search returns immediately."""

        async def _do_update() -> None:
            """Execute the salience increment in the background."""
            try:
                self.repo.increment_salience(ids)
            except Exception:
                logger.warning("Background salience update failed — will retry next search")

        task = asyncio.create_task(_do_update())
        # Hold a reference so it isn't garbage-collected mid-flight
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def create_entity(self, params: EntityCreateParams) -> EntityCommitReceipt:
        """Creates an entity node in the graph."""

        # Concurrency Control: Project-Project-Level Lock
        # We lock based on the target project to prevent race conditions
        # within the same project space.
        project_id = params.project_id

        async with self.lock_manager.lock(project_id):
            # Validate Dynamic Type
            if not self.ontology.is_valid_type(params.node_type):
                raise ValueError(
                    f"Invalid memory type: '{params.node_type}'. "
                    f"Allowed types: {self.ontology.list_types()}"
                )

            start_time = datetime.now()
            logger.info(f"Creating entity: {params.name} ({params.node_type})")

            props = params.properties.copy()
            props["id"] = params.properties.get("id") or str(uuid.uuid4())
            props.update(
                {
                    "name": params.name,
                    "node_type": params.node_type,
                    "project_id": params.project_id,
                    "certainty": params.certainty,
                    "evidence": params.evidence,
                    "salience_score": 1.0,
                    "retrieval_count": 0,
                    "occurred_at": params.properties.get(
                        "occurred_at", datetime.now(UTC).isoformat()
                    ),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )

            # Compute embedding (AI Layer)
            desc = props.get("description", "")
            text_to_embed = f"{params.name} {params.node_type} {desc}"
            embedding = self.embedder.encode(text_to_embed)

            # 1. Write to Graph (FalkorDB) - Source of Truth for Structure
            # Note: We do NOT pass embedding to repo anymore.
            node_props = self.repo.create_node(params.node_type, props)

            # 2. Write to Vector Engine (Qdrant) - Source of Truth for Search
            # We use the ID returned/confirmed by the Repo
            # (in case of deduplication, we might update vector)
            node_id = str(node_props["id"])

            # Determine valid payload (flat dict preferred for vector DBs)
            payload = {
                "name": params.name,
                "node_type": params.node_type,
                "project_id": params.project_id,
            }
            await self.vector_store.upsert(id=node_id, vector=embedding, payload=payload)

            # 3. Link to most recent entity in same project via PRECEDED_BY
            try:
                prev = self.repo.get_most_recent_entity(project_id)
                if prev and prev.get("id") != node_id:
                    self.repo.create_edge(
                        prev["id"],
                        node_id,
                        "PRECEDED_BY",
                        {"created_at": datetime.now(UTC).isoformat()},
                    )
            except Exception:
                logger.warning("PRECEDED_BY link failed — entity created without temporal link")

            # Execute creation (Redundant variable assignment removed from logic flow above)
            result = node_props

            final_id = str(result["id"])
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            status = "created"  # or "merged"

            # 3. Get total count (for receipt)
            total_count = self.repo.get_total_node_count()

            return EntityCommitReceipt(
                id=final_id,
                name=params.name,
                status="committed",  # Schema limit, keeping "committed"
                # for simplicity unless schema updated.
                operation_time_ms=duration,
                total_memory_count=total_count,
                message=f"Successfully {status} '{params.name}' in the Infinite Graph.",
            )

    async def create_relationship(self, params: RelationshipCreateParams) -> dict[str, Any]:
        """Creates a typed relationship between two entities."""

        # Concurrency: Best effort lock on source entity's project
        # We need to look up the source entity to find the project.
        # This adds a read, but ensures safety.
        source_node = self.repo.get_node(params.from_entity)

        if source_node and "project_id" in source_node:
            # Manually manage lock context since it's conditional
            # actually, let's use the context manager.
            # We can't conditionally enter "with".
            # So we use the helper logic.
            pass

        # Simplified approach: If we can't determine project easily, we proceed without lock
        # OR we enforce fetching. Safety first -> Fetch.

        project_id = source_node.get("project_id") if source_node else None

        # Helper to run logic
        async def _do_create() -> dict[str, Any]:
            """Execute relationship creation inside the optional lock."""
            logger.info(
                f"Creating relationship: {params.from_entity} "
                f"-[{params.relationship_type}]-> {params.to_entity}"
            )

            props = params.properties.copy()
            props["confidence"] = params.confidence
            props["weight"] = params.weight
            props["created_at"] = datetime.now(UTC).isoformat()
            if "id" not in props:
                props["id"] = str(uuid.uuid4())

            res = self.repo.create_edge(
                params.from_entity, params.to_entity, params.relationship_type, props
            )
            if not res:
                return {"error": "Could not create relationship. Check entity IDs."}
            return res

        if project_id:
            async with self.lock_manager.lock(project_id):
                return await _do_create()
        else:
            return await _do_create()

    async def update_entity(self, params: EntityUpdateParams) -> dict[str, Any]:
        """Updates properties of an existing entity."""

        # Fetch for Locking
        existing_node = self.repo.get_node(params.entity_id)
        if not existing_node:
            return {"error": "Entity not found"}

        project_id = existing_node.get("project_id")

        async def _do_update() -> dict[str, Any]:
            """Execute entity update inside the optional lock."""
            logger.info(f"Updating entity: {params.entity_id}")

            props = params.properties.copy()
            timestamp = datetime.now(UTC).isoformat()
            props["updated_at"] = timestamp

            # Embed re-calculation logic (Business Logic)
            embedding = None
            # If name or node_type or description changed, re-embed.
            # We don't have old description here unless we used existing_node above.
            # We have existing_node!

            # Check if embedding relevant fields changed
            # This is a good optimization opportunity too.
            # For correctness, let's assume if properties are passed, we might need update.
            # But params.properties usually contains only changes? No, it's a replacement or merge?
            # The tool def says "properties to update".

            # Simple logic: Always re-embed if name/desc/type are in props, or just do it.
            # To do it properly we need the FULL content.
            # existing_node has current state. props has updates.
            merged_props = existing_node.copy()
            merged_props.update(props)

            desc = merged_props.get("description", "")
            name = merged_props.get("name", "")
            node_type = merged_props.get("node_type", "Entity")

            text_to_embed = f"{name} {node_type} {desc}"
            embedding = self.embedder.encode(text_to_embed)

            # 1. Update Graph
            updated_node = self.repo.update_node(params.entity_id, props)

            # 2. Update Vector Store
            payload = {
                "name": name,
                "node_type": node_type,
                "project_id": project_id,  # Keep existing project_id
            }
            # qdrant upsert overwrites payload. We need full payload?
            # Yes, standard behavior.
            await self.vector_store.upsert(id=params.entity_id, vector=embedding, payload=payload)

            return updated_node  # type: ignore[no-any-return]

        if project_id:
            async with self.lock_manager.lock(project_id):
                return await _do_update()
        else:
            # Should not happen for valid entities, but fallback
            return await _do_update()

    async def delete_entity(self, params: EntityDeleteParams) -> dict[str, Any]:
        """Deletes an entity."""

        existing_node = self.repo.get_node(params.entity_id)
        if not existing_node:
            return {"error": "Entity not found"}

        project_id = existing_node.get("project_id")

        async def _do_delete() -> dict[str, Any]:
            """Execute entity deletion inside the optional lock."""
            logger.info(f"Deleting entity: {params.entity_id} ({params.reason})")

            if params.soft_delete:
                # 1. Archive in Graph
                self.repo.update_node(
                    params.entity_id,
                    {"status": "archived", "archived_at": datetime.now(UTC).isoformat()},
                )
                # 2. Remove from Vector Store (so it's not searchable)
                try:
                    await self.vector_store.delete(params.entity_id)
                except Exception as e:
                    logger.warning(f"Failed to delete vector for {params.entity_id}: {e}")
                return {"status": "archived", "id": params.entity_id}
            else:
                # Hard Delete
                self.repo.delete_node(params.entity_id)
                try:
                    await self.vector_store.delete(params.entity_id)
                except Exception as e:
                    logger.warning(f"Failed to delete vector for {params.entity_id}: {e}")
                    # In a real scenario we might want to re-raise or handle gracefully.
                    # B904 requires raise ... from e if we re-raised.
                    # Here we suppress, so no raise.
                    # Wait, B904 applies if we RAISE.
                    # Let's check where the error actually is.
                    pass
                return {"status": "deleted", "id": params.entity_id}

        if project_id:
            async with self.lock_manager.lock(project_id):
                return await _do_delete()
        else:
            return await _do_delete()

    async def delete_relationship(self, params: RelationshipDeleteParams) -> dict[str, Any]:
        """Deletes a relationship."""
        self.repo.delete_edge(params.relationship_id)
        return {"status": "deleted", "id": params.relationship_id}

    async def add_observation(self, params: ObservationParams) -> dict[str, Any]:
        """Adds an observation node linked to an entity."""
        # This is strictly custom cypher logic not easily genericized in Repo yet.
        # But we can assume Repo has 'execute_cypher'.
        # Or better: construct a custom Repo method.
        # For now, let's use execute_cypher to migrate quickly.

        obs_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        query = """
        MATCH (e) WHERE e.id = $entity_id
        CREATE (o:Observation {
            id: $obs_id,
            content: $content,
            certainty: $certainty,
            evidence: $evidence,
            created_at: $timestamp,
            project_id: e.project_id
        })
        CREATE (e)-[:HAS_OBSERVATION]->(o)
        RETURN o
        """
        params_dict = {
            "entity_id": params.entity_id,
            "obs_id": obs_id,
            "content": params.content,
            "certainty": params.certainty,
            "evidence": params.evidence,
            "timestamp": timestamp,
        }
        res = self.repo.execute_cypher(query, params_dict)
        if not res.result_set:
            return {"error": "Entity not found"}
        return cast(dict[str, Any], res.result_set[0][0].properties)

    async def start_session(self, params: SessionStartParams) -> dict[str, Any]:
        """Create a new session node in the graph.

        Sessions act as temporal anchors: each session gets an occurred_at
        timestamp and is linked to the previous session via PRECEDED_BY.
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        props = {
            "id": session_id,
            "project_id": params.project_id,
            "focus": params.focus,
            "status": "active",
            "created_at": timestamp,
            "occurred_at": timestamp,
            "node_type": "Session",
        }

        # Create session and link to previous session in one atomic query.
        # The OPTIONAL MATCH ensures this works even if no previous session exists.
        query = """
        OPTIONAL MATCH (prev:Session {project_id: $project_id, status: 'closed'})
        WITH prev ORDER BY prev.occurred_at DESC LIMIT 1
        CREATE (s:Session)
        SET s = $props
        WITH s, prev
        FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
            CREATE (prev)-[:PRECEDED_BY {created_at: $timestamp}]->(s)
        )
        RETURN s
        """
        res = self.repo.execute_cypher(
            query,
            {
                "props": props,
                "project_id": params.project_id,
                "timestamp": timestamp,
            },
        )
        return cast(dict[str, Any], res.result_set[0][0].properties)

    async def end_session(self, params: SessionEndParams) -> dict[str, Any]:
        """Close a session and record its summary and outcomes."""
        timestamp = datetime.now(UTC).isoformat()
        query = """
        MATCH (s:Session)
        WHERE s.id = $session_id
        SET s.status = 'closed'
        SET s.ended_at = $timestamp
        SET s.summary = $summary
        SET s.outcomes = $outcomes
        RETURN s
        """
        res = self.repo.execute_cypher(
            query,
            {
                "session_id": params.session_id,
                "timestamp": timestamp,
                "summary": params.summary,
                "outcomes": params.outcomes,
            },
        )
        if not res.result_set:
            return {"error": "Session not found"}
        return cast(dict[str, Any], res.result_set[0][0].properties)

    async def record_breakthrough(self, params: BreakthroughParams) -> dict[str, Any]:
        """Create a Breakthrough node linked to its originating session."""
        # Logic: create breakthrough node.

        b_id = str(uuid.uuid4())
        props = {
            "id": b_id,
            "name": params.name,
            "moment": params.moment,
            "analogy": params.analogy_used or "",
            "project_id": "meta",
            "certainty": "confirmed",
            "created_at": datetime.now(UTC).isoformat(),
            "node_type": "Breakthrough",  # Keep schema consistency
        }
        res = self.repo.create_node("Breakthrough", props)
        if params.session_id:
            self.repo.create_edge(params.session_id, b_id, "BREAKTHROUGH_IN", {"confidence": 1.0})

        return res  # type: ignore[no-any-return]

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
        # vector_store needs to support filtering
        vector_results = await self.vector_store.search(
            vector=vec, limit=10, filter={"created_at_lt": as_of}
        )

        if not vector_results:
            return []

        # Hydrate from Graph
        ids = [item["_id"] for item in vector_results]
        graph_data = self.repo.get_subgraph(ids, depth=0)

        # Flatten
        nodes = [node for node in graph_data["nodes"]]
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
    ) -> list[SearchResult]:
        """Search for entities, optionally routing via QueryRouter.

        When ``strategy`` is provided, dispatches via :class:`QueryRouter`:
        - ``'auto'`` — auto-classify intent from the query text
        - ``'semantic'`` / ``'associative'`` / ``'temporal'`` / ``'relational'``
        When ``strategy`` is None, uses direct vector search (default).
        """
        if not query:
            return []

        # Route through QueryRouter if strategy is specified
        if strategy is not None:
            intent = None if strategy == "auto" else QueryIntent(strategy)
            results = await self.router.route(
                query,
                self,
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

        # 2. Search Vector Store
        # 2. Search Vector Store with optional project filter
        search_filter: dict[str, Any] | None = None
        if project_id:
            search_filter = {"project_id": project_id}

        if mmr:
            vector_results = await self.vector_store.search_mmr(
                vector=vec,
                limit=limit,
                filter=search_filter,
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
                        distance=1.0 - v_res["_score"],  # Approximation for Cosine
                        salience_score=salience_map.get(
                            node_id, node_props.get("salience_score", 0.0)
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
    ) -> list[SearchResult]:
        """Spreading-activation search: vector → graph spread → composite rank.

        1. Vector search to find initial seed nodes.
        2. Activate seeds and spread energy through the graph.
        3. Hydrate candidate entities from graph.
        4. Composite rank with configurable weights (env var / per-query).
        """
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
        activation_map = self.activation_engine.spread(activation_map, decay=decay, max_hops=max_hops)

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

    async def query_timeline(
        self,
        params: TemporalQueryParams,
    ) -> list[dict[str, Any]]:
        """Fetch entities within a time window, ordered by occurred_at."""
        return self.repo.query_timeline(  # type: ignore[no-any-return]
            start=params.start.isoformat(),
            end=params.end.isoformat(),
            limit=params.limit,
            project_id=params.project_id,
        )

    async def get_temporal_neighbors(
        self,
        entity_id: str,
        direction: str = "both",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find entities connected by temporal edges."""
        return self.repo.get_temporal_neighbors(  # type: ignore[no-any-return]
            entity_id=entity_id,
            direction=direction,
            limit=limit,
        )

    async def get_bottles(
        self,
        params: BottleQueryParams,
    ) -> list[dict[str, Any]]:
        """Query 'Bottle' entities (messages to future self)."""
        return self.repo.get_bottles(  # type: ignore[no-any-return]
            limit=params.limit,
            search_text=params.search_text,
            before_date=params.before_date.isoformat() if params.before_date else None,
            after_date=params.after_date.isoformat() if params.after_date else None,
            project_id=params.project_id,
        )

    async def get_graph_health(self) -> dict[str, Any]:
        """Compute graph health metrics including community count.

        Merges repository-level stats (nodes, edges, density, orphans, avg_degree)
        with clustering-based community count.
        """
        from .clustering import ClusteringService  # noqa: PLC0415

        health = self.repo.get_graph_health()

        # Compute community count via clustering
        community_count = 0
        cs = ClusteringService()
        if health["total_nodes"] >= cs.min_samples:
            try:
                nodes = self.repo.get_all_nodes(limit=2000)
                clusters = cs.cluster_nodes(nodes)
                community_count = len(clusters)
            except Exception:
                logger.warning("Clustering failed during health check — community_count=0")

        health["community_count"] = community_count
        return health  # type: ignore[no-any-return]

    async def detect_structural_gaps(self, params: GapDetectionParams) -> list[dict[str, Any]]:
        """Detect structural gaps between knowledge clusters.

        Runs clustering, computes cross-cluster connectivity vs similarity,
        and generates research prompts for each identified gap.
        """
        from .clustering import ClusteringService, detect_gaps  # noqa: PLC0415

        # 1. Cluster all nodes
        nodes = self.repo.get_all_nodes(limit=2000)
        cs = ClusteringService()
        clusters = cs.cluster_nodes(nodes)

        if len(clusters) < 2:  # noqa: PLR2004
            return []

        # 2. Get all edges for cross-cluster connectivity
        edges = self.repo.get_all_edges()

        # 3. Detect gaps
        gaps = detect_gaps(
            clusters,
            edges,
            min_similarity=params.min_similarity,
            max_edges=params.max_edges,
        )

        # 4. Build results with research prompts
        results: list[dict[str, Any]] = []
        for gap in gaps[: params.limit]:
            # Find cluster names for context
            ca = next((c for c in clusters if c.id == gap.cluster_a_id), None)
            cb = next((c for c in clusters if c.id == gap.cluster_b_id), None)
            a_names = [n.get("name", "?") for n in (ca.nodes[:3] if ca else [])]
            b_names = [n.get("name", "?") for n in (cb.nodes[:3] if cb else [])]

            prompt = (
                f"These knowledge areas seem related (similarity: {gap.similarity:.0%}) "
                f"but are poorly connected ({gap.edge_count} edges).\n"
                f"Cluster A: {', '.join(a_names)}\n"
                f"Cluster B: {', '.join(b_names)}\n"
                f"Consider: What connections exist between these topics? "
                f"Are there shared concepts, dependencies, or patterns?"
            )

            results.append(
                {
                    "cluster_a_id": gap.cluster_a_id,
                    "cluster_b_id": gap.cluster_b_id,
                    "similarity": gap.similarity,
                    "edge_count": gap.edge_count,
                    "suggested_bridges": gap.suggested_bridges,
                    "research_prompt": prompt,
                }
            )

        return results

    async def archive_entity(self, entity_id: str) -> dict[str, Any]:
        """Archive an entity (logical hide)."""
        return self.repo.update_node(entity_id, {"status": "archived"})  # type: ignore[no-any-return]

    async def prune_stale(self, days: int = 30) -> dict[str, Any]:
        """Hard delete archived entities older than N days."""

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        query = """
        MATCH (n:Entity)
        WHERE n.status = 'archived' AND n.archived_at < $cutoff
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        res = self.repo.execute_cypher(query, {"cutoff": cutoff})
        count = res.result_set[0][0] if res.result_set else 0
        return {"status": "success", "deleted_count": count}

    async def analyze_graph(
        self, algorithm: Literal["pagerank", "louvain"] = "pagerank"
    ) -> list[dict[str, Any]]:
        """
        Runs graph algorithms to find key entities or communities.

        Args:
            algorithm: 'pagerank' for influence, 'louvain' for communities.
        """
        # Delegate logic to repo? Repo should have execute_algo?
        # I didn't add nice wrappers in Repo yet, but I added execute_cypher.
        # Let's use execute_cypher for now to keep movement fast.

        results = []
        if algorithm == "pagerank":
            try:
                self.repo.execute_cypher("CALL algo.pageRank('Entity', 'rank')")
                res = self.repo.execute_cypher(
                    "MATCH (n:Entity) RETURN n ORDER BY n.rank DESC LIMIT 10"
                )
                for row in res.result_set:
                    node = row[0]
                    results.append(
                        {
                            "name": node.properties.get("name"),
                            "rank": node.properties.get("rank"),
                            "type": (
                                next(iter(set(node.labels) - {"Entity"}))
                                if (set(node.labels) - {"Entity"})
                                else "Entity"
                            ),
                        }
                    )
            except Exception as e:
                logger.error(f"PageRank failed: {e}")
                return [{"error": str(e)}]

        elif algorithm == "louvain":
            try:
                self.repo.execute_cypher("CALL algo.louvain('Entity', 'community')")
                q = """
                MATCH (n:Entity)
                RETURN n.community, count(n) as size, collect(n.name)[..5] as members
                ORDER BY size DESC LIMIT 5
                """
                res = self.repo.execute_cypher(q)
                for row in res.result_set:
                    results.append({"community_id": row[0], "size": row[1], "members": row[2]})
            except Exception as e:
                logger.error(f"Louvain failed: {e}")
                return [{"error": str(e)}]
        return results

    async def get_stale_entities(self, days: int = 30) -> list[dict[str, Any]]:
        """Identify entities not modified/accessed in N days."""

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        query = """
        MATCH (n:Entity)
        WHERE n.updated_at < $cutoff AND (n.status IS NULL OR n.status <> 'archived')
        RETURN n
        ORDER BY n.updated_at ASC
        LIMIT 20
        """
        res = self.repo.execute_cypher(query, {"cutoff": cutoff})
        entities = [row[0].properties for row in res.result_set]
        for e in entities:
            e.pop("embedding", None)
        return entities

    async def consolidate_memories(self, entity_ids: list[str], summary: str) -> dict[str, Any]:
        """Merge multiple entities into a new Consolidated concept."""
        # 1. Create new Idea via calling create_entity (which uses repo)
        # WAIT: The whole point was to avoid self-calls.
        # Correct pattern: Call repo directly.

        new_id = str(uuid.uuid4())

        params = EntityCreateParams(
            name=f"Consolidated Memory: {summary[:20]}...",
            node_type="Concept",
            project_id="memory_maintenance",
            properties={"description": summary, "id": new_id, "is_consolidated": True},
        )

        # Compute embedding
        text_to_embed = f"{params.name} {params.node_type} {summary}"
        embedding = self.embedder.encode(text_to_embed)

        props = params.properties.copy()
        props.update(
            {
                "name": params.name,
                "node_type": params.node_type,
                "project_id": params.project_id,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

        # 1. Write Graph
        new_node_props = self.repo.create_node("Concept", props)

        # 2. Write Vector
        payload = {
            "name": params.name,
            "node_type": params.node_type,
            "project_id": params.project_id,
        }
        await self.vector_store.upsert(id=new_id, vector=embedding, payload=payload)

        # 2. Link old to new
        for old_id in entity_ids:
            try:
                # Direct Repo Call
                link_props = {
                    "confidence": 1.0,
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self.repo.create_edge(old_id, new_id, "PART_OF", link_props)

                # Archive old (Direct Repo Call)
                self.repo.update_node(
                    old_id,
                    {"status": "archived", "archived_at": datetime.now(UTC).isoformat()},
                )
            except Exception:  # noqa: S112
                continue

        return new_node_props  # type: ignore[no-any-return]

    def create_memory_type(
        self, name: str, description: str, required_properties: list[str] | None = None
    ) -> dict[str, Any]:
        """Registers a new memory type in the ontology."""
        if required_properties is None:
            required_properties = []
        self.ontology.add_type(name, description, required_properties)
        return {
            "name": name,
            "description": description,
            "required_properties": required_properties,
            "status": "active",
        }

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
        # We assume search returns SearchResult objects or dicts.
        # Codebase uses SearchResult pydantic model in 'search' return type annotation
        # but implementation returns List[SearchResult].
        anchors = await self.search(query, limit=5)

        if not anchors:
            return {"nodes": [], "edges": []}

        anchor_ids = [a.id for a in anchors]

        # 2. Expand Subgraph
        hologram = self.repo.get_subgraph(anchor_ids, depth)

        # 3. Assemble and Optimize
        # Convert list to map for easier dedup if needed,
        # but repo returns deduplicated lists usually.
        # But we need to separate nodes and edges for optimization.

        raw_nodes = hologram.get("nodes", [])
        raw_edges = hologram.get("edges", [])

        # Sanitization: Strip embeddings to prevent context flood
        # This is critical as nodes recovered from vector store mirror the embedding
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
