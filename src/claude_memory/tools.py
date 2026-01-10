import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, cast

from .interfaces import Embedder
from .repository import MemoryRepository
from .schema import (
    BreakthroughParams,
    EntityCommitReceipt,
    EntityCreateParams,
    EntityDeleteParams,
    EntityUpdateParams,
    ObservationParams,
    RelationshipCreateParams,
    RelationshipDeleteParams,
    SearchResult,
    SessionEndParams,
    SessionStartParams,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(
        self,
        embedding_service: Embedder,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
    ) -> None:
        self.repo = MemoryRepository(host, port, password)
        self.repo.ensure_indices()
        self.embedder = embedding_service

    async def create_entity(self, params: EntityCreateParams) -> EntityCommitReceipt:
        """Creates an entity node in the graph."""
        start_time = datetime.now()
        logger.info(f"Creating entity: {params.name} ({params.node_type})")

        props = params.properties.copy()
        import uuid

        props["id"] = params.properties.get("id") or str(uuid.uuid4())
        props.update(
            {
                "name": params.name,
                "node_type": params.node_type,
                "project_id": params.project_id,
                "certainty": params.certainty,
                "evidence": params.evidence,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Compute embedding (AI Layer)
        desc = props.get("description", "")
        embedding = self.embedder.encode(params.name + " " + str(desc))

        # We don't store embedding in props dictionary passed to repo, repo handles it.
        if "embedding" in props:
            props.pop("embedding")

        # Execute creation
        self.repo.create_node(params.node_type, props, embedding)

        # Calculate Receipt Data
        duration = (datetime.now() - start_time).total_seconds() * 1000
        total_count = self.repo.get_total_node_count()

        return EntityCommitReceipt(
            id=props["id"],
            name=params.name,
            status="committed",
            operation_time_ms=duration,
            total_memory_count=total_count,
            message=f"Successfully committed '{params.name}' to the Infinite Graph.",
        )

    async def create_relationship(self, params: RelationshipCreateParams) -> Dict[str, Any]:
        """Creates a typed relationship between two entities."""
        logger.info(
            f"Creating relationship: {params.from_entity} -[{params.relationship_type}]-> {params.to_entity}"
        )

        props = params.properties.copy()
        props["confidence"] = params.confidence
        props["created_at"] = datetime.now(timezone.utc).isoformat()
        import uuid

        if "id" not in props:
            props["id"] = str(uuid.uuid4())

        res = self.repo.create_edge(
            params.from_entity, params.to_entity, params.relationship_type, props
        )
        if not res:
            return {"error": "Could not create relationship. Check entity IDs."}
        return cast(Dict[str, Any], res)

    async def update_entity(self, params: EntityUpdateParams) -> Dict[str, Any]:
        """Updates properties of an existing entity."""
        logger.info(f"Updating entity: {params.entity_id}")

        props = params.properties.copy()
        timestamp = datetime.now(timezone.utc).isoformat()
        props["updated_at"] = timestamp

        # Embed re-calculation logic (Business Logic)
        embedding = None
        if "name" in props or "description" in props:
            # Need to fetch old if partial update?
            # Repo doesn't support 'fetch before update' easily.
            # We can use execute_cypher or add 'get_node'.
            # For strict decoupling, we should ask repo for the node.

            # Helper to get node props
            q = "MATCH (n:Entity {id: $id}) RETURN n"
            res = self.repo.execute_cypher(q, {"id": params.entity_id})
            if res.result_set:
                curr = res.result_set[0][0].properties
                curr_name = curr.get("name", "")
                curr_desc = curr.get("description", "")

                new_name = props.get("name", curr_name)
                new_desc = props.get("description", curr_desc)

                embedding = self.embedder.encode(new_name + " " + str(new_desc))

        result = self.repo.update_node(params.entity_id, props, embedding)
        if not result:
            return {"error": "Entity not found"}
        return cast(Dict[str, Any], result)

    async def delete_entity(self, params: EntityDeleteParams) -> Dict[str, Any]:
        """Deletes (or soft deletes) an entity."""
        logger.info(f"Deleting entity: {params.entity_id} (Soft: {params.soft_delete})")

        if self.repo.delete_node(params.entity_id, params.soft_delete, params.reason):
            status = "soft_deleted" if params.soft_delete else "hard_deleted"
            return {"status": status, "id": params.entity_id}
        else:
            return {"error": "Entity not found"}

    async def delete_relationship(self, params: RelationshipDeleteParams) -> Dict[str, Any]:
        """Deletes a relationship."""
        self.repo.delete_edge(params.relationship_id)
        return {"status": "deleted", "id": params.relationship_id}

    async def add_observation(self, params: ObservationParams) -> Dict[str, Any]:
        """Adds an observation node linked to an entity."""
        # This is strictly custom cypher logic not easily genericized in Repo yet.
        # But we can assume Repo has 'execute_cypher'.
        # Or better: construct a custom Repo method.
        # For now, let's use execute_cypher to migrate quickly.

        import uuid

        obs_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

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
        return cast(Dict[str, Any], res.result_set[0][0].properties)

    async def start_session(self, params: SessionStartParams) -> Dict[str, Any]:
        import uuid

        session_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        props = {
            "id": session_id,
            "project_id": params.project_id,
            "focus": params.focus,
            "status": "active",
            "created_at": timestamp,
            "node_type": "Session",
        }
        # Use generic create_node? Label 'Session'
        # Session isn't :Entity in implicit schema?
        # create_node adds :Entity label.
        # Custom cypher is safer for specific labels.

        query = """
        CREATE (s:Session)
        SET s = $props
        RETURN s
        """
        res = self.repo.execute_cypher(query, {"props": props})
        return cast(Dict[str, Any], res.result_set[0][0].properties)

    async def end_session(self, params: SessionEndParams) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
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
        return cast(Dict[str, Any], res.result_set[0][0].properties)

    async def record_breakthrough(self, params: BreakthroughParams) -> Dict[str, Any]:
        # Logic: create breakthrough node.
        import uuid

        b_id = str(uuid.uuid4())
        props = {
            "id": b_id,
            "name": params.name,
            "moment": params.moment,
            "analogy": params.analogy_used or "",
            "project_id": "meta",
            "certainty": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "node_type": "Breakthrough",  # Keep schema consistency
        }
        # Creating as Entity?
        # Schema implies Breakthrough is a node type.
        # Let's use generic create_node, it adds :Entity.
        # Wait, if we use repo.create_node("Breakthrough", props), it becomes :Breakthrough:Entity
        # That fits the pattern.
        return cast(Dict[str, Any], self.repo.create_node("Breakthrough", props))

    async def get_neighbors(
        self, entity_id: str, depth: int = 1, limit: int = 20
    ) -> List[Dict[str, Any]]:
        # Repo doesn't have get_neighbors yet (I missed adding it in last step? No, I listed it).
        # Actually I didn't verify if I added it to Repo class file content.
        # Let's check Repo content.
        # I suspect I might have missed it or need to implement execute_cypher for it.
        # Use execute_cypher for now.
        if depth < 1:
            depth = 1
        query = f"""
        MATCH (n)-[*1..{depth}]-(m)
        WHERE n.id = $entity_id
        RETURN distinct m
        LIMIT $limit
        """
        res = self.repo.execute_cypher(query, {"entity_id": entity_id, "limit": limit})
        return [row[0].properties for row in res.result_set if row]

    async def traverse_path(self, from_id: str, to_id: str) -> List[Dict[str, Any]]:
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
                    path_data.append(node.properties)
        return path_data

    async def find_cross_domain_patterns(
        self, entity_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find nodes in different projects connected to this entity."""
        query = """
        MATCH (n:Entity {id: $entity_id})
        MATCH (n)-[*1..3]-(m:Entity)
        WHERE m.project_id <> n.project_id
        RETURN distinct m
        LIMIT $limit
        """
        res = self.repo.execute_cypher(query, {"entity_id": entity_id, "limit": limit})
        return [row[0].properties for row in res.result_set if row]

    async def get_evolution(self, entity_id: str) -> List[Dict[str, Any]]:
        """Retrieve the evolution (history/observations) of an entity."""
        query = """
        MATCH (e:Entity {id: $entity_id})-[:HAS_OBSERVATION]->(o)
        RETURN o
        ORDER BY o.created_at DESC
        """
        res = self.repo.execute_cypher(query, {"entity_id": entity_id})
        return [row[0].properties for row in res.result_set if row]

    async def point_in_time_query(self, query_text: str, as_of: str) -> List[Dict[str, Any]]:
        """Execute a search considering only knowledge known before `as_of`."""
        vec = self.embedder.encode(query_text)

        # Brute force (logic kept for now as temporal filter is complex with vector index)
        # Or we can scan all and filter.
        bf_query = """
        MATCH (n:Entity)
        WHERE n.embedding IS NOT NULL
        AND n.created_at <= $as_of
        RETURN n
        """
        res = self.repo.execute_cypher(bf_query, {"as_of": as_of})

        import numpy as np
        from scipy.spatial.distance import cosine

        candidates = []
        target_vec = np.array(vec)

        for row in res.result_set:
            node = row[0]
            embedding_list = node.properties.get("embedding")
            if not embedding_list:
                continue

            node_vec = np.array(embedding_list)
            if len(node_vec) != len(target_vec):
                continue

            dist = cosine(target_vec, node_vec)
            candidates.append((node.properties, 1.0 - dist))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:10]]

    async def archive_entity(self, entity_id: str) -> Dict[str, Any]:
        """Archive an entity (logical hide)."""
        return cast(
            Dict[str, Any],
            self.repo.update_node(entity_id, {"status": "archived"}),
        )

    async def prune_stale(self, days: int = 30) -> Dict[str, Any]:
        """Hard delete archived entities older than N days."""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

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
    ) -> List[Dict[str, Any]]:
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
                                list(set(node.labels) - {"Entity"})[0]
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

    async def get_stale_entities(self, days: int = 30) -> List[Dict[str, Any]]:
        """Identify entities not modified/accessed in N days."""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = """
        MATCH (n:Entity)
        WHERE n.updated_at < $cutoff AND (n.status IS NULL OR n.status <> 'archived')
        RETURN n
        ORDER BY n.updated_at ASC
        LIMIT 20
        """
        res = self.repo.execute_cypher(query, {"cutoff": cutoff})
        return [row[0].properties for row in res.result_set]

    async def consolidate_memories(self, entity_ids: List[str], summary: str) -> Dict[str, Any]:
        """Merge multiple entities into a new Consolidated concept."""
        # 1. Create new Idea via calling create_entity (which uses repo)
        # WAIT: The whole point was to avoid self-calls.
        # Correct pattern: Call repo directly.

        import uuid

        new_id = str(uuid.uuid4())

        params = EntityCreateParams(
            name=f"Consolidated Memory: {summary[:20]}...",
            node_type="Concept",
            project_id="memory_maintenance",
            properties={"description": summary, "id": new_id, "is_consolidated": True},
        )
        # Use repo directly
        # But we need embedding.
        embedding = self.embedder.encode(params.name + " " + summary)

        props = params.properties.copy()
        props.update(
            {
                "name": params.name,
                "node_type": params.node_type,
                "project_id": params.project_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        new_node_props = self.repo.create_node("Concept", props, embedding)

        # 2. Link old to new
        for old_id in entity_ids:
            try:
                # Direct Repo Call
                link_props = {
                    "confidence": 1.0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self.repo.create_edge(old_id, new_id, "PART_OF", link_props)

                # Archive old (Direct Repo Call)
                self.repo.update_node(
                    old_id,
                    {"status": "archived", "archived_at": datetime.now(timezone.utc).isoformat()},
                )
            except Exception:
                continue

        return new_node_props  # type: ignore

    async def search(
        self, query: str, project_id: Optional[str] = None, limit: int = 10
    ) -> List[SearchResult]:
        """Performs hybrid search."""
        vec = self.embedder.encode(query)

        # Delegate to repository vector search
        try:
            filters = {"project_id": project_id} if project_id else None
            rows = self.repo.query_vector(vec, limit, filters)

            results = []
            for row in rows:
                node = row[0]
                score = row[1]
                results.append(
                    SearchResult(
                        id=node.properties.get("id", "unknown"),
                        name=node.properties.get("name", "Unnamed"),
                        node_type=(
                            list(set(node.labels) - {"Entity"})[0]
                            if (set(node.labels) - {"Entity"})
                            else "Entity"
                        ),
                        project_id=node.properties.get("project_id", "unknown"),
                        score=float(score),
                        distance=float(score),
                    )
                )

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        return results

    async def get_hologram(self, query: str, depth: int = 1) -> Dict[str, Any]:
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

        return hologram  # type: ignore
