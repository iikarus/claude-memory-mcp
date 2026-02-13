"""Analysis & maintenance operations for the Exocortex memory system.

Provides graph analytics, gap detection, stale entity management,
memory consolidation, and ontology management.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from claude_memory.graph_algorithms import compute_louvain, compute_pagerank

if TYPE_CHECKING:  # pragma: no cover
    from .interfaces import Embedder, VectorStore
    from .ontology import OntologyManager
    from .repository import MemoryRepository
    from .schema import GapDetectionParams

logger = logging.getLogger(__name__)


class AnalysisMixin:
    """Graph health / gaps / stale / consolidation — mixed into MemoryService."""

    repo: "MemoryRepository"
    embedder: "Embedder"
    vector_store: "VectorStore"
    ontology: "OntologyManager"

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

    async def system_diagnostics(self) -> dict[str, Any]:
        """E-5: Unified system diagnostics — graph, vector, and split-brain."""
        result: dict[str, Any] = {}

        # Graph section
        result["graph"] = self.repo.get_graph_health()

        # Vector section
        vector_section: dict[str, Any] = {}
        try:
            vector_section["count"] = await self.vector_store.count()
            vector_section["error"] = None
        except Exception as exc:
            vector_section["count"] = None
            vector_section["error"] = str(exc)
        result["vector"] = vector_section

        # Split-brain detection
        split: dict[str, Any] = {}
        if vector_section["error"] is not None:
            split["status"] = "unavailable"
            split["graph_only_count"] = 0
            split["graph_only_ids"] = []
        else:
            try:
                graph_ids = set(self.repo.get_all_node_ids())
                vector_ids = set(await self.vector_store.list_ids())
                graph_only = graph_ids - vector_ids
                split["status"] = "ok" if not graph_only else "drift"
                split["graph_only_count"] = len(graph_only)
                split["graph_only_ids"] = sorted(graph_only)
            except Exception as exc:
                split["status"] = "error"
                split["graph_only_count"] = 0
                split["graph_only_ids"] = []
                logger.error("split_brain_check_failed: %s", exc)
        result["split_brain"] = split

        return result

    async def reconnect(
        self,
        project_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """E-4: Session reconnect — structured briefing for a returning agent."""
        now = datetime.now(UTC)
        since = (now - timedelta(days=1)).isoformat()
        until = now.isoformat()

        recent = self.repo.query_timeline(
            start=since,
            end=until,
            limit=limit,
            project_id=project_id,
        )

        health = self.repo.get_graph_health()

        return {
            "recent_entities": recent,
            "health": health,
            "window": {"start": since, "end": until},
        }

    async def detect_structural_gaps(self, params: "GapDetectionParams") -> list[dict[str, Any]]:
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
        """Archive an entity (logical hide).

        Deletes Qdrant vector BEFORE graph update to prevent ghost search results.
        """
        await self.vector_store.delete(entity_id)
        return self.repo.update_node(entity_id, {"status": "archived"})  # type: ignore[no-any-return]

    async def prune_stale(self, days: int = 30) -> dict[str, Any]:
        """Hard delete archived entities older than N days.

        Deletes Qdrant vectors BEFORE graph nodes to prevent orphan vectors.
        Order: SELECT IDs → delete vectors → DETACH DELETE graph nodes.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        # Step 1: SELECT IDs of entities to prune (don't delete yet)
        select_query = """
        MATCH (n:Entity)
        WHERE n.status = 'archived' AND n.archived_at < $cutoff
        RETURN n.id
        """
        res = self.repo.execute_cypher(select_query, {"cutoff": cutoff})
        entity_ids = [row[0] for row in res.result_set] if res.result_set else []

        if not entity_ids:
            return {"status": "success", "deleted_count": 0}

        # Step 2: Delete Qdrant vectors FIRST (fail-safe order)
        for entity_id in entity_ids:
            await self.vector_store.delete(entity_id)

        # Step 3: DETACH DELETE from FalkorDB
        delete_query = """
        MATCH (n:Entity)
        WHERE n.status = 'archived' AND n.archived_at < $cutoff
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        del_res = self.repo.execute_cypher(delete_query, {"cutoff": cutoff})
        count = del_res.result_set[0][0] if del_res.result_set else 0
        return {"status": "success", "deleted_count": count}

    async def analyze_graph(
        self, algorithm: Literal["pagerank", "louvain"] = "pagerank"
    ) -> list[dict[str, Any]]:
        """Run graph algorithms to find key entities or communities.

        Computes algorithms in Python using adjacency data fetched via Cypher.
        FalkorDB does not provide built-in algo.pageRank/algo.louvain procedures.

        Args:
            algorithm: 'pagerank' for influence, 'louvain' for communities.
        """
        # Fetch all nodes
        node_res = self.repo.execute_cypher("MATCH (n:Entity) RETURN n")
        if not node_res.result_set:
            return []

        nodes = {row[0].properties["name"]: row[0] for row in node_res.result_set}
        node_names = list(nodes.keys())

        # Fetch all edges
        edge_res = self.repo.execute_cypher(
            "MATCH (a:Entity)-[r]->(b:Entity) RETURN a.name, b.name"
        )
        edges = [(row[0], row[1]) for row in edge_res.result_set] if edge_res.result_set else []

        if algorithm == "pagerank":
            return compute_pagerank(nodes, node_names, edges)
        elif algorithm == "louvain":
            return compute_louvain(nodes, node_names, edges)
        return []

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
        from .schema import EntityCreateParams  # noqa: PLC0415

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

        # 3. Link old to new
        errors: list[str] = []
        for old_id in entity_ids:
            try:
                link_props = {
                    "confidence": 1.0,
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self.repo.create_edge(old_id, new_id, "PART_OF", link_props)

                # Archive old
                self.repo.update_node(
                    old_id,
                    {"status": "archived", "archived_at": datetime.now(UTC).isoformat()},
                )
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.error("consolidate_memories: failed to archive %s: %s", old_id, e)
                errors.append(f"{old_id}: {e}")

        result = dict(new_node_props) if not isinstance(new_node_props, dict) else new_node_props
        if errors:
            result["consolidation_errors"] = errors
        return result

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
