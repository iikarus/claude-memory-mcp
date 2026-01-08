from unittest.mock import AsyncMock, MagicMock

import pytest

from claude_memory.clustering import Cluster
from claude_memory.librarian import LibrarianAgent


@pytest.fixture
def mock_memory_service() -> MagicMock:
    service = MagicMock()
    service.repo = MagicMock()
    service.repo.get_all_nodes = MagicMock()
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
