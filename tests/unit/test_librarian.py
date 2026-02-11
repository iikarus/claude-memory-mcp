from unittest.mock import AsyncMock, MagicMock

import pytest

from claude_memory.clustering import Cluster
from claude_memory.librarian import LibrarianAgent


@pytest.fixture
def mock_memory_service() -> MagicMock:
    service = MagicMock()
    service.repo = MagicMock()
    service.repo.get_all_nodes = MagicMock()
    service.repo.get_all_edges = MagicMock(return_value=[])
    service.repo.create_node = MagicMock()
    service.consolidate_memories = AsyncMock()
    service.prune_stale = AsyncMock()
    service.clustering = MagicMock()  # Not used by agent instantly, but good to have
    return service


@pytest.fixture
def mock_clustering_service() -> MagicMock:
    service = MagicMock()
    service.cluster_nodes = MagicMock()
    service.min_samples = 2
    return service


@pytest.mark.asyncio
async def test_librarian_cycle_success(
    mock_memory_service: MagicMock, mock_clustering_service: MagicMock
) -> None:
    # Setup Data
    mock_memory_service.repo.get_all_nodes.return_value = [
        {"id": "1", "name": "A"},
        {"id": "2", "name": "B"},
    ]

    mock_cluster = Cluster(
        id=0,
        nodes=[{"id": "1", "name": "A"}, {"id": "2", "name": "B"}],
        centroid=[0.1, 0.1],
        cohesion_score=0.95,
    )
    mock_clustering_service.cluster_nodes.return_value = [mock_cluster]

    mock_memory_service.consolidate_memories.return_value = {"id": "new_concept"}
    mock_memory_service.prune_stale.return_value = {"deleted_count": 5}

    # Init Agent
    agent = LibrarianAgent(mock_memory_service, mock_clustering_service)

    # Run
    report = await agent.run_cycle()

    # Assert
    assert report["clusters_found"] == 1
    assert report["consolidations_created"] == 1
    assert report["deleted_stale"] == 5
    # Only 1 cluster → no gaps possible
    assert report["gaps_detected"] == 0
    assert report["gap_reports_stored"] == 0

    mock_memory_service.repo.get_all_nodes.assert_called_once()
    mock_clustering_service.cluster_nodes.assert_called_once()
    mock_memory_service.consolidate_memories.assert_awaited_once()
    mock_memory_service.prune_stale.assert_awaited_once_with(days=60)


@pytest.mark.asyncio
async def test_librarian_cycle_no_nodes(
    mock_memory_service: MagicMock, mock_clustering_service: MagicMock
) -> None:
    mock_memory_service.repo.get_all_nodes.return_value = []

    agent = LibrarianAgent(mock_memory_service, mock_clustering_service)
    report = await agent.run_cycle()

    assert report["clusters_found"] == 0
    mock_clustering_service.cluster_nodes.assert_not_called()


@pytest.mark.asyncio
async def test_librarian_cycle_gap_detection(
    mock_memory_service: MagicMock, mock_clustering_service: MagicMock
) -> None:
    """run_cycle detects gaps and stores GapReport entities."""
    from unittest.mock import patch as mock_patch

    from claude_memory.clustering import StructuralGap

    # Enough nodes for 2 clusters
    nodes = [{"id": f"n{i}", "name": f"Node{i}", "embedding": [float(i)]} for i in range(6)]
    mock_memory_service.repo.get_all_nodes.return_value = nodes

    # 2 clusters with similar centroids
    ca = Cluster(id=0, nodes=nodes[:3], centroid=[1.0, 0.0], cohesion_score=0.1)
    cb = Cluster(id=1, nodes=nodes[3:], centroid=[0.95, 0.1], cohesion_score=0.1)
    mock_clustering_service.cluster_nodes.return_value = [ca, cb]

    # No cross-cluster edges → gap expected
    mock_memory_service.repo.get_all_edges.return_value = []
    mock_memory_service.consolidate_memories.return_value = {"id": "c1"}
    mock_memory_service.prune_stale.return_value = {"deleted_count": 0}

    # Mock detect_gaps to return a known gap
    mock_gap = StructuralGap(
        cluster_a_id=0,
        cluster_b_id=1,
        similarity=0.85,
        edge_count=0,
        suggested_bridges=[],
    )

    with mock_patch("claude_memory.librarian.detect_gaps", return_value=[mock_gap]):
        agent = LibrarianAgent(mock_memory_service, mock_clustering_service)
        report = await agent.run_cycle()

    # Gap detection assertions
    assert report["gaps_detected"] == 1
    assert report["gap_reports_stored"] == 1

    # Verify GapReport entity was created with correct positional args
    mock_memory_service.repo.create_node.assert_called_once()
    call_args = mock_memory_service.repo.create_node.call_args
    label = call_args[0][0]
    properties = call_args[0][1]
    assert label == "GapReport"
    assert properties["entity_type"] == "GapReport"
    assert "detected_at" in properties
    assert properties["similarity"] == 0.85
