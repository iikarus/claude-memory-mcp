from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.schema import SearchResult
from claude_memory.tools import MemoryService


@pytest.fixture
def mock_service() -> Any:
    with (
        patch("claude_memory.embedding.EmbeddingService") as MockEmbedder,
        patch("claude_memory.repository.FalkorDB"),
    ):

        service = MemoryService(embedding_service=MockEmbedder.return_value)
        # Mock the repository client interactions
        service.repo.client = MagicMock()
        service.repo.select_graph = MagicMock()
        service.repo.select_graph.return_value = service.repo.client

        yield service


@pytest.mark.asyncio
async def test_get_hologram_orchestration(mock_service: Any) -> None:
    """Verify get_hologram calls search then get_subgraph."""
    # Setup Search Mock
    mock_service.search = AsyncMock()
    mock_service.search.return_value = [
        SearchResult(
            id="1",
            name="A",
            score=0.9,
            content="A",
            distance=0.1,
            node_type="Entity",
            project_id="p1",
        ),
        SearchResult(
            id="2",
            name="B",
            score=0.8,
            content="B",
            distance=0.2,
            node_type="Entity",
            project_id="p1",
        ),
    ]

    # Setup Repository Mock
    mock_service.repo.get_subgraph = MagicMock()
    mock_service.repo.get_subgraph.return_value = {
        "nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        "edges": [{"source": "1", "target": "3"}],
    }

    # Execute
    result = await mock_service.get_hologram("test query", depth=2)

    # Assertions
    mock_service.search.assert_awaited_once_with("test query", limit=5)
    mock_service.repo.get_subgraph.assert_called_once_with(["1", "2"], 2)
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 1


def test_repository_get_subgraph_parsing(mock_service: Any) -> None:
    """Verify get_subgraph parses Cypher result correctly."""
    # Mock the graph.query response
    mock_result_set = MagicMock()

    # expected query output:
    # RETURN collect(edges), collect(nodes)

    node1_map = {"id": "1", "labels": ["Entity"], "properties": {"id": "1", "name": "Node1"}}
    node2_map = {"id": "2", "labels": ["Entity"], "properties": {"id": "2", "name": "Node2"}}

    edge1_map = {"id": "e1", "source": "1", "target": "2", "type": "CONNECTED_TO", "properties": {}}

    # row[0] is edges, row[1] is nodes
    mock_row = [[edge1_map], [node1_map, node2_map]]  # Edges  # Nodes

    mock_result_set.result_set = [mock_row]
    mock_service.repo.client.query.return_value = mock_result_set

    # Execute
    result = mock_service.repo.get_subgraph(["1"])

    # Verify
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
    # Verify the extracted properties
    names = sorted([n["name"] for n in result["nodes"]])
    assert names == ["Node1", "Node2"]
    assert result["edges"][0]["type"] == "CONNECTED_TO"
