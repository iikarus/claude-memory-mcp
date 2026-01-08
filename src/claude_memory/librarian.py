import logging
from typing import Any, Dict, List

from .clustering import ClusteringService
from .tools import MemoryService

logger = logging.getLogger(__name__)


class LibrarianAgent:
    """
    Autonomous agent responsible for memory maintenance, clustering, and consolidation.
    "The Librarian" brings order to chaos.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        clustering_service: ClusteringService,
    ):
        self.memory = memory_service
        self.clustering = clustering_service

    async def run_cycle(self) -> Dict[str, Any]:
        """
        Executes a full maintenance cycle.
        1. Fetch all nodes.
        2. Cluster them.
        3. Consolidate dense clusters.
        4. Prune stale data.
        """
        logger.info("Starting Librarian Maintenance Cycle...")
        report: Dict[str, Any] = {
            "clusters_found": 0,
            "consolidations_created": 0,
            "deleted_stale": 0,
            "errors": [],
        }

        # 1. Fetch
        # We need direct access to repo for bulk fetch, or add a tool.
        # Added get_all_nodes to repo in previous step.
        try:
            nodes = self.memory.repo.get_all_nodes(limit=2000)
            logger.info(f"Fetched {len(nodes)} nodes for analysis.")
        except Exception as e:
            logger.error(f"Failed to fetch nodes: {e}")
            report["errors"].append(str(e))
            return report

        if len(nodes) < self.clustering.min_samples:
            logger.info("Not enough nodes to form clusters.")
            return report

        # 2. Cluster
        clusters = self.clustering.cluster_nodes(nodes)
        report["clusters_found"] = len(clusters)

        # 3. Consolidate
        for cluster in clusters:
            # Heuristic: Only consolidate high cohesion clusters
            # For now, we consolidate ALL valid clusters as a demo.
            # In production, we'd check cluster.cohesion_score

            summary = self._synthesize_summary(cluster.nodes)
            entity_ids = [n["id"] for n in cluster.nodes if "id" in n]

            logger.info(f"Consolidating Cluster {cluster.id} with {len(entity_ids)} nodes.")
            try:
                # Call the existing tool logic
                res = await self.memory.consolidate_memories(entity_ids, summary)
                if res and "id" in res:
                    report["consolidations_created"] += 1
            except Exception as e:
                logger.error(f"Failed to consolidate cluster {cluster.id}: {e}")
                report["errors"].append(f"Cluster {cluster.id}: {str(e)}")

        # 4. Prune Stale
        try:
            prune_res = await self.memory.prune_stale(days=60)
            report["deleted_stale"] = prune_res.get("deleted_count", 0)
        except Exception as e:
            report["errors"].append(f"Prune: {str(e)}")

        logger.info("Librarian Cycle Complete.")
        return report

    def _synthesize_summary(self, nodes: List[Dict[str, Any]]) -> str:
        """
        Mock LLM Synthesis.
        In a real system, this would send node contents to Claude to generate a summary.
        """
        # Extract names/titles
        titles = [n.get("name", "Untitled") for n in nodes[:3]]
        topic = ", ".join(titles)
        return f"Consolidated Architecture regarding: {topic} and {len(nodes)-3} others."
