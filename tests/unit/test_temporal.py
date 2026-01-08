from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.tools import MemoryService


@pytest.fixture  # type: ignore
def memory_service() -> Generator[MemoryService, None, None]:
    with patch("claude_memory.repository.FalkorDB"):
        service = MemoryService()
        service.repo.client = MagicMock()
        service.repo.client.select_graph.return_value = MagicMock()
        yield service


@pytest.mark.asyncio  # type: ignore
async def test_get_evolution(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    # Mock observations
    obs1 = MagicMock()
    obs1.properties = {"id": "o1", "created_at": "2023-01-01"}
    obs2 = MagicMock()
    obs2.properties = {"id": "o2", "created_at": "2023-01-02"}

    graph.query.return_value.result_set = [[obs2], [obs1]]

    result = await memory_service.get_evolution("e1")

    assert len(result) == 2
    assert result[0]["id"] == "o2"
    assert "ORDER BY o.created_at DESC" in graph.query.call_args[0][0]


@pytest.mark.asyncio  # type: ignore
async def test_point_in_time_query(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    # Mock result from the "Brute Force" query
    node1 = MagicMock()
    # Mock embedding [1.0, 0.0, ...]
    node1.properties = {
        "id": "e1",
        "name": "Match",
        "embedding": [1.0] * 1024,
        "created_at": "2023-01-01",
    }

    graph.query.return_value.result_set = [[node1]]

    # Mock SentenceTransformer to return consistent vector
    with patch("claude_memory.tools.SentenceTransformer") as MockST:
        encoder = MockST.return_value
        encoder.encode.return_value.tolist.return_value = [1.0] * 1024

        result = await memory_service.point_in_time_query("test", "2023-12-31")

    assert len(result) == 1
    assert result[0]["id"] == "e1"
    assert "n.created_at <= $as_of" in graph.query.call_args[0][0]


@pytest.mark.asyncio  # type: ignore
async def test_archive_entity(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    mock_node = MagicMock()
    mock_node.properties = {"id": "e1", "status": "archived"}
    graph.query.return_value.result_set = [[mock_node]]

    result = await memory_service.archive_entity("e1")

    assert result["status"] == "archived"

    # Check Cypher structure
    cypher = graph.query.call_args[0][0]
    assert "SET n += $props" in cypher

    # Check params
    call_params = graph.query.call_args[0][1]
    assert call_params["props"]["status"] == "archived"


@pytest.mark.asyncio  # type: ignore
async def test_prune_stale(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    graph.query.return_value.result_set = [[5]]  # 5 deleted nodes

    result = await memory_service.prune_stale(days=30)

    assert result["deleted_count"] == 5
    assert "DETACH DELETE n" in graph.query.call_args[0][0]
