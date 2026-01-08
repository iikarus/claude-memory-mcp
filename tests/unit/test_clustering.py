from typing import Any, Dict, List

import pytest

from claude_memory.clustering import ClusteringService


@pytest.fixture
def sample_nodes() -> List[Dict[str, Any]]:
    # Create two clear clusters in 2D space (mocked as embeddings)
    # Cluster 1: Near (0,0)
    # Cluster 2: Near (10,10)
    return [
        {"id": "1", "name": "A", "embedding": [0.1, 0.1]},
        {"id": "2", "name": "B", "embedding": [0.2, 0.2]},
        {"id": "3", "name": "C", "embedding": [0.1, 0.15]},
        {"id": "4", "name": "X", "embedding": [10.1, 10.1]},
        {"id": "5", "name": "Y", "embedding": [10.2, 10.2]},
        {"id": "6", "name": "Z", "embedding": [10.1, 10.15]},
        {"id": "7", "name": "Noise", "embedding": [5.0, 5.0]},  # Outlier
    ]


def test_clustering_dbscan(sample_nodes: List[Dict[str, Any]]) -> None:
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
