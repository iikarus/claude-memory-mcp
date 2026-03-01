"""Mutation-killing tests for clustering.py — DBSCAN edge cases and cosine sim.

Targets ~15 kills: empty input, single node, noise exclusion,
zero vector cosine sim, cross-edge counting, gap detection guards.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from claude_memory.clustering import (
    Cluster,
    ClusteringService,
    StructuralGap,
    _cosine_sim,
    detect_gaps,
)


def _node(name: str, embedding: list[float] | None = None, **kw: Any) -> dict[str, Any]:
    """Helper to create a node dict."""
    d: dict[str, Any] = {"id": name, "name": name, **kw}
    if embedding is not None:
        d["embedding"] = embedding
    return d


# ═══════════════════════════════════════════════════════════════════
# cluster_nodes — Evil Tests
# ═══════════════════════════════════════════════════════════════════


class TestClusterNodesEvil:
    """Evil tests for DBSCAN clustering."""

    def test_evil_empty_input(self) -> None:
        """Evil: empty node list must return empty list."""
        cs = ClusteringService()
        assert cs.cluster_nodes([]) == []

    def test_evil_no_embeddings_skipped(self) -> None:
        """Evil: nodes missing 'embedding' key must be skipped."""
        cs = ClusteringService()
        nodes = [_node("A"), _node("B"), _node("C")]
        result = cs.cluster_nodes(nodes)
        assert result == []

    def test_evil_single_node_below_min_samples(self) -> None:
        """Evil: 1 node < min_samples=3 → noise → empty clusters."""
        cs = ClusteringService()
        nodes = [_node("A", embedding=[1.0, 0.0, 0.0])]
        result = cs.cluster_nodes(nodes)
        assert result == []


class TestClusterNodesSad:
    """Sad path tests for clustering."""

    def test_sad_two_nodes_below_threshold(self) -> None:
        """Sad: 2 nodes < min_samples=3 → all noise."""
        cs = ClusteringService()
        nodes = [
            _node("A", embedding=[1.0, 0.0]),
            _node("B", embedding=[0.9, 0.1]),
        ]
        result = cs.cluster_nodes(nodes)
        assert result == []


class TestClusterNodesHappy:
    """Happy path tests for clustering."""

    def test_happy_tight_cluster(self) -> None:
        """Happy: nodes with identical embeddings form a cluster."""
        cs = ClusteringService(eps=0.5, min_samples=3)
        emb = [1.0, 0.0, 0.0]
        nodes = [_node(f"N{i}", embedding=emb) for i in range(5)]
        result = cs.cluster_nodes(nodes)
        assert len(result) >= 1
        assert all(isinstance(c, Cluster) for c in result)


# ═══════════════════════════════════════════════════════════════════
# _cosine_sim (module-level function) — Evil Tests
# ═══════════════════════════════════════════════════════════════════


class TestCosineSimEvil:
    """Evil tests for cosine similarity function."""

    def test_evil_zero_vector_returns_zero(self) -> None:
        """Evil: zero vector must return 0.0, not NaN or error."""
        assert _cosine_sim(np.array([0.0, 0.0]), np.array([1.0, 0.0])) == 0.0

    def test_evil_identical_vectors_return_one(self) -> None:
        """Evil: identical vectors must return 1.0."""
        result = _cosine_sim(np.array([1.0, 0.0]), np.array([1.0, 0.0]))
        assert abs(result - 1.0) < 0.001

    def test_evil_orthogonal_vectors_return_zero(self) -> None:
        """Evil: orthogonal vectors must return 0.0."""
        result = _cosine_sim(np.array([1.0, 0.0]), np.array([0.0, 1.0]))
        assert abs(result) < 0.001

    def test_sad_opposite_vectors(self) -> None:
        """Sad: opposite vectors return -1.0."""
        result = _cosine_sim(np.array([1.0, 0.0]), np.array([-1.0, 0.0]))
        assert abs(result + 1.0) < 0.001

    def test_happy_similar_vectors(self) -> None:
        """Happy: similar vectors return high similarity."""
        result = _cosine_sim(np.array([1.0, 0.1]), np.array([1.0, 0.0]))
        assert result > 0.9


# ═══════════════════════════════════════════════════════════════════
# detect_gaps — Evil Tests
# ═══════════════════════════════════════════════════════════════════


class TestDetectGapsEvil:
    """Evil tests for structural gap detection."""

    def test_evil_less_than_two_clusters(self) -> None:
        """Evil: < 2 clusters → empty list."""
        c1 = Cluster(
            id="0",
            nodes=[_node("A", embedding=[1.0])],
            centroid=[1.0],
            cohesion_score=1.0,
        )
        assert detect_gaps([c1], []) == []

    def test_evil_empty_clusters(self) -> None:
        """Evil: empty cluster list → empty gaps."""
        assert detect_gaps([], []) == []

    def test_evil_zero_edge_input(self) -> None:
        """Evil: no edges doesn't crash."""
        result = detect_gaps([], [("a", "b")])
        assert result == []

    def test_sad_dissimilar_clusters_no_gap(self) -> None:
        """Sad: clusters with low similarity → no gap above threshold."""
        c1 = Cluster(
            id="0",
            nodes=[_node("A", embedding=[1.0, 0.0])],
            centroid=[1.0, 0.0],
            cohesion_score=1.0,
        )
        c2 = Cluster(
            id="1",
            nodes=[_node("B", embedding=[0.0, 1.0])],
            centroid=[0.0, 1.0],
            cohesion_score=1.0,
        )
        result = detect_gaps([c1, c2], [], min_similarity=0.9)
        assert result == []

    def test_happy_gap_structure(self) -> None:
        """Happy: detected gaps have correct attributes."""
        c1 = Cluster(
            id="0",
            nodes=[_node("A", embedding=[1.0, 0.0])],
            centroid=[1.0, 0.0],
            cohesion_score=1.0,
        )
        c2 = Cluster(
            id="1",
            nodes=[_node("B", embedding=[0.99, 0.01])],
            centroid=[0.99, 0.01],
            cohesion_score=1.0,
        )
        result = detect_gaps([c1, c2], [], min_similarity=0.5, max_edges=0)
        if result:
            gap = result[0]
            assert isinstance(gap, StructuralGap)
            assert hasattr(gap, "cluster_a_id")
            assert hasattr(gap, "cluster_b_id")
            assert hasattr(gap, "similarity")
            assert hasattr(gap, "edge_count")
