from typing import Any

import pytest

from claude_memory.clustering import Cluster, ClusteringService, detect_gaps


@pytest.fixture
def sample_nodes() -> list[dict[str, Any]]:
    # Create two clear clusters in 2D space (mocked as embeddings)
    # Cluster 1: Near (0,0)
    # Cluster 2: Near (10,10)
    return [
        {"id": "1", "name": "A", "embedding": [1.0, 0.0]},
        {"id": "2", "name": "B", "embedding": [0.9, 0.1]},
        {"id": "3", "name": "C", "embedding": [0.95, 0.05]},
        {"id": "4", "name": "X", "embedding": [0.0, 1.0]},
        {"id": "5", "name": "Y", "embedding": [0.1, 0.9]},
        {"id": "6", "name": "Z", "embedding": [0.05, 0.95]},
        {"id": "7", "name": "Noise", "embedding": [-0.5, -0.5]},  # Opposite direction
    ]


def test_clustering_dbscan(sample_nodes: list[dict[str, Any]]) -> None:
    # Use small epsilon sufficient to group the dense points but exclude noise
    # Euclidean distance between (0.1,0.1) and (0.2,0.2) is small (~0.14)
    service = ClusteringService(eps=0.5, min_samples=2)

    clusters = service.cluster_nodes(sample_nodes)

    assert len(clusters) == 2

    # Sort by ID to ensure consistent checking
    clusters.sort(key=lambda x: x.id)

    c1 = clusters[0]
    c2 = clusters[1]

    assert len(c1.nodes) == 3
    assert len(c2.nodes) == 3

    # Verify contents
    ids1 = sorted([n["id"] for n in c1.nodes])
    assert ids1 == ["1", "2", "3"]

    ids2 = sorted([n["id"] for n in c2.nodes])
    assert ids2 == ["4", "5", "6"]

    # Noise node '7' should not be in any cluster


# ─── Phase 15B: Structural Gap Detection Tests ─────────────────────


def _make_cluster(cid: int, nodes: list[dict[str, Any]], centroid: list[float]) -> Cluster:
    """Helper to build a Cluster fixture."""
    return Cluster(id=cid, nodes=nodes, centroid=centroid, cohesion_score=0.1)


def test_detect_gaps_disconnected_similar() -> None:
    """Similar clusters with no edges between them should be flagged as a gap."""
    # Two clusters with very similar centroids (both near [1,0])
    ca = _make_cluster(
        0,
        [{"id": "a1", "name": "A1", "embedding": [1.0, 0.0]}],
        [1.0, 0.1],
    )
    cb = _make_cluster(
        1,
        [{"id": "b1", "name": "B1", "embedding": [0.95, 0.1]}],
        [0.95, 0.15],
    )
    # No edges
    gaps = detect_gaps([ca, cb], edges=[], min_similarity=0.7)
    assert len(gaps) == 1
    assert gaps[0].cluster_a_id == 0
    assert gaps[0].cluster_b_id == 1
    assert gaps[0].similarity >= 0.7
    assert gaps[0].edge_count == 0
    assert len(gaps[0].suggested_bridges) >= 1


def test_detect_gaps_well_connected() -> None:
    """Clusters with many cross-cluster edges should NOT be flagged."""
    ca = _make_cluster(0, [{"id": "a1"}], [1.0, 0.1])
    cb = _make_cluster(1, [{"id": "b1"}], [0.95, 0.15])
    # 5 edges between them — well above max_edges=2
    edges = [{"source": "a1", "target": "b1"}] * 5
    gaps = detect_gaps([ca, cb], edges, min_similarity=0.7, max_edges=2)
    assert len(gaps) == 0


def test_detect_gaps_dissimilar() -> None:
    """Clusters with low centroid similarity should be ignored (not a gap)."""
    ca = _make_cluster(0, [{"id": "a1"}], [1.0, 0.0])
    cb = _make_cluster(1, [{"id": "b1"}], [0.0, 1.0])  # Orthogonal
    gaps = detect_gaps([ca, cb], edges=[], min_similarity=0.7)
    assert len(gaps) == 0


def test_detect_gaps_single_cluster() -> None:
    """Fewer than 2 clusters should return no gaps."""
    ca = _make_cluster(0, [{"id": "a1"}], [1.0, 0.0])
    gaps = detect_gaps([ca], edges=[])
    assert gaps == []
