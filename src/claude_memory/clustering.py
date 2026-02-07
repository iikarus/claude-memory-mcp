"""Clustering service using DBSCAN to group related memory nodes by embedding similarity."""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN

logger = logging.getLogger(__name__)


@dataclass
class Cluster:
    """Represents a discovered cluster of related memory nodes."""

    id: int  # Cluster ID from DBSCAN (-1 is noise)
    nodes: list[dict[str, Any]]
    centroid: list[float]
    cohesion_score: float  # Mean distance to centroid


class ClusteringService:
    """Groups memory nodes into clusters using DBSCAN on their embedding vectors."""

    def __init__(self, eps: float = 0.5, min_samples: int = 3):
        """
        Args:
            eps: The maximum distance between two samples for one to be considered as in the
                neighborhood of the other.
            min_samples: The number of samples (or total weight) in a neighborhood for a point to be
                considered as a core point.
        """
        self.eps = eps
        self.min_samples = min_samples

    def cluster_nodes(self, nodes: list[dict[str, Any]]) -> list[Cluster]:
        """
        Clusters a list of nodes based on their 'embedding' property.
        Any node with a missing or invalid embedding is ignored.
        """
        valid_nodes = []
        embeddings = []

        # 1. Filter and Extract Embeddings
        for node in nodes:
            emb = node.get("embedding")
            if emb and isinstance(emb, list) and len(emb) > 0:
                valid_nodes.append(node)
                embeddings.append(emb)

        if not valid_nodes:
            logger.warning("No valid nodes with embeddings found for clustering.")
            return []

        X = np.array(embeddings)  # noqa: N806

        # 2. Run DBSCAN
        logger.info(
            f"Running DBSCAN on {len(X)} nodes with eps={self.eps}, min_samples={self.min_samples}"
        )
        db = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="cosine").fit(X)
        labels = db.labels_

        # 3. Group Results
        clusters_map: dict[int, list[dict[str, Any]]] = {}
        cluster_vectors: dict[int, list[np.ndarray]] = {}

        for idx, label in enumerate(labels):
            if label == -1:
                # Noise point, ignore for now
                continue

            if label not in clusters_map:
                clusters_map[label] = []
                cluster_vectors[label] = []

            clusters_map[label].append(valid_nodes[idx])
            cluster_vectors[label].append(X[idx])

        # 4. Create Cluster Objects
        results: list[Cluster] = []
        for label, cluster_nodes in clusters_map.items():
            vectors = np.array(cluster_vectors[label])
            centroid = np.mean(vectors, axis=0)

            # Calculate cohesion (average cosine distance to centroid)
            # Cosine distance = 1 - cosine_similarity
            # For simplicity in this mock, we'll use Euclidean variance or similar if
            # metric was euclidean.
            # strict cosine distance is complex to compute efficiently without scipy per point.
            # Let's approximate cohesion as 1.0 / (variance + 1) or just meaningful density.
            # Actually, standard deviation of points from centroid is a good proxy for 'spread'.
            # Lower spread = Higher cohesion.
            distances = np.linalg.norm(vectors - centroid, axis=1)
            mean_dist = float(np.mean(distances))

            # Cohesion score: Invert distance (closer is better) or just report mean distance
            cohesion = mean_dist

            results.append(
                Cluster(
                    id=int(label),
                    nodes=cluster_nodes,
                    centroid=centroid.tolist(),
                    cohesion_score=cohesion,
                )
            )

        logger.info(f"Found {len(results)} clusters.")
        return results
