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
async def test_get_neighbors(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    # Mock result for get_neighbors
    mock_node = MagicMock()
    mock_node.properties = {"id": "n2", "name": "Neighbor"}

    graph.query.return_value.result_set = [[mock_node]]

    result = await memory_service.get_neighbors("n1", depth=1)

    assert len(result) == 1
    assert result[0]["id"] == "n2"
    assert "MATCH (n)-[*1..1]-(m)" in graph.query.call_args[0][0]


@pytest.mark.asyncio  # type: ignore
async def test_traverse_path(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    # Mock result for traverse_path
    mock_path = MagicMock()

    # Create fake nodes
    node1 = MagicMock()
    node1.properties = {"id": "start"}
    node2 = MagicMock()
    node2.properties = {"id": "end"}

    mock_path.nodes = [node1, node2]

    # Result set: [[path_obj]]
    graph.query.return_value.result_set = [[mock_path]]

    result = await memory_service.traverse_path("start", "end")

    assert len(result) == 2
    assert result[0]["id"] == "start"
    assert result[1]["id"] == "end"

    assert "shortestPath" in graph.query.call_args[0][0]


@pytest.mark.asyncio  # type: ignore
async def test_find_cross_domain_patterns(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    # Mock result (list of nodes)
    mock_node = MagicMock()
    mock_node.properties = {"id": "n3", "project_id": "other_proj"}
    graph.query.return_value.result_set = [[mock_node]]

    result = await memory_service.find_cross_domain_patterns("n1")

    assert len(result) == 1
    assert result[0]["project_id"] == "other_proj"
    # Check Cypher for cross domain logic
    assert "WHERE m.project_id <> n.project_id" in graph.query.call_args[0][0]
