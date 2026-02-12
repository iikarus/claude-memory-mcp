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
            "Running DBSCAN on %d nodes with eps=%s, min_samples=%s",
            len(X),
            self.eps,
            self.min_samples,
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

        logger.info("Found %d clusters.", len(results))
        return results


# ─── Structural Gap Detection ───────────────────────────────────────


@dataclass
class StructuralGap:
    """A pair of clusters that are semantically similar but poorly connected."""

    cluster_a_id: int
    cluster_b_id: int
    similarity: float
    edge_count: int
    suggested_bridges: list[dict[str, Any]]


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _build_cross_edge_counts(
    clusters: list[Cluster], edges: list[dict[str, Any]]
) -> dict[tuple[int, int], int]:
    """Count edges crossing between each pair of clusters."""
    node_to_cluster: dict[str, int] = {}
    for cluster in clusters:
        for node in cluster.nodes:
            node_id = node.get("id", "")
            if node_id:
                node_to_cluster[node_id] = cluster.id

    cross_edges: dict[tuple[int, int], int] = {}
    for edge in edges:
        src_cluster = node_to_cluster.get(edge.get("source", ""))
        tgt_cluster = node_to_cluster.get(edge.get("target", ""))
        if src_cluster is not None and tgt_cluster is not None and src_cluster != tgt_cluster:
            pair = (min(src_cluster, tgt_cluster), max(src_cluster, tgt_cluster))
            cross_edges[pair] = cross_edges.get(pair, 0) + 1

    return cross_edges


def detect_gaps(
    clusters: list[Cluster],
    edges: list[dict[str, Any]],
    min_similarity: float = 0.7,
    max_edges: int = 2,
) -> list[StructuralGap]:
    """Detect structural gaps between clusters.

    A gap exists when two clusters are semantically similar (centroid cosine
    similarity >= min_similarity) but have few cross-cluster edges (<= max_edges).

    Args:
        clusters: Clusters from ClusteringService.cluster_nodes().
        edges: Edge list from repository.get_all_edges() [{source, target}].
        min_similarity: Minimum centroid similarity to consider a gap.
        max_edges: Maximum cross-cluster edges to qualify as a gap.

    Returns:
        List of StructuralGap objects, sorted by similarity descending.
    """
    if len(clusters) < 2:  # noqa: PLR2004
        return []

    cross_edges = _build_cross_edge_counts(clusters, edges)

    gaps: list[StructuralGap] = []
    for i, ca in enumerate(clusters):
        for cb in clusters[i + 1 :]:
            sim = _cosine_sim(np.array(ca.centroid), np.array(cb.centroid))
            if sim < min_similarity:
                continue

            pair_key = (min(ca.id, cb.id), max(ca.id, cb.id))
            edge_count = cross_edges.get(pair_key, 0)
            if edge_count > max_edges:
                continue

            bridges = _find_bridge_candidates(ca, cb, top_n=2)
            gaps.append(
                StructuralGap(
                    cluster_a_id=ca.id,
                    cluster_b_id=cb.id,
                    similarity=round(sim, 4),
                    edge_count=edge_count,
                    suggested_bridges=bridges,
                )
            )

    gaps.sort(key=lambda g: g.similarity, reverse=True)
    return gaps


def _find_bridge_candidates(ca: Cluster, cb: Cluster, top_n: int = 2) -> list[dict[str, Any]]:
    """Find the closest node pairs between two clusters as bridge candidates."""
    if not ca.nodes or not cb.nodes:
        return []

    # Get embeddings for nodes in both clusters
    a_nodes = [(n, n.get("embedding")) for n in ca.nodes if n.get("embedding")]
    b_nodes = [(n, n.get("embedding")) for n in cb.nodes if n.get("embedding")]

    if not a_nodes or not b_nodes:
        return []

    bridges: list[dict[str, Any]] = []
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []

    for a_node, a_emb in a_nodes:
        for b_node, b_emb in b_nodes:
            sim = _cosine_sim(np.array(a_emb), np.array(b_emb))
            scored.append((sim, a_node, b_node))

    scored.sort(key=lambda x: x[0], reverse=True)

    for sim, a_node, b_node in scored[:top_n]:
        bridges.append(
            {
                "from_id": a_node.get("id", ""),
                "from_name": a_node.get("name", ""),
                "to_id": b_node.get("id", ""),
                "to_name": b_node.get("name", ""),
                "similarity": round(sim, 4),
            }
        )

    return bridges
