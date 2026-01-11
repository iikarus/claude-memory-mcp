from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.tools import MemoryService


@pytest.fixture
def memory_service(mock_vector_store: Any) -> Generator[MemoryService, None, None]:
    with (
        patch("claude_memory.repository.FalkorDB"),
        patch("claude_memory.embedding.EmbeddingService") as MockEmbedder,
    ):

        # Setup Embedder Mock
        mock_instance = MagicMock()
        MockEmbedder.return_value = mock_instance
        # Default behavior
        mock_instance.encode.return_value = [0.1] * 1024

        service = MemoryService(embedding_service=mock_instance, vector_store=mock_vector_store)
        service.repo.client = MagicMock()
        service.repo.client.select_graph.return_value = MagicMock()

        # Ensure service uses our mock
        service.embedder = mock_instance

        yield service


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_point_in_time_query(memory_service: Any, mock_vector_store: Any) -> None:
    # Setup mocks
    # Search should return vector hits
    mock_vector_store.search.return_value = [
        {"_id": "e1", "_score": 0.9, "name": "Match"},
    ]

    # Repo get_subgraph should hydrate nodes
    # We access repo via memory_service.repo
    memory_service.repo.get_subgraph = MagicMock(
        return_value={
            "nodes": [
                {"id": "e1", "name": "Match", "created_at": "2023-01-01"},
            ]
        }
    )

    # Execute
    result = await memory_service.point_in_time_query("test", "2023-12-31")

    # Verify
    assert len(result) == 1
    assert result[0]["id"] == "e1"

    # Check filter passed to vector store
    mock_vector_store.search.assert_called_once()
    call_kwargs = mock_vector_store.search.call_args.kwargs
    assert call_kwargs["filter"] == {"created_at_lt": "2023-12-31"}


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_prune_stale(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    graph.query.return_value.result_set = [[5]]  # 5 deleted nodes

    result = await memory_service.prune_stale(days=30)

    assert result["deleted_count"] == 5
    assert "DETACH DELETE n" in graph.query.call_args[0][0]
