from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.tools import MemoryService


@pytest.fixture
def mock_repo() -> Generator[Any, None, None]:
    with patch("claude_memory.tools.MemoryRepository") as mock_repo_cls:
        repo_instance = mock_repo_cls.return_value
        # Default returns
        repo_instance.create_node.return_value = {"id": "mock-id", "name": "Mock Node"}
        repo_instance.create_edge.return_value = {"id": "mock-rel-id"}
        repo_instance.update_node.return_value = {"id": "mock-id"}
        repo_instance.execute_cypher.return_value = MagicMock(result_set=[])
        yield repo_instance


@pytest.fixture
def memory_service(mock_repo: Any) -> Any:
    # Initialize service with mocks
    with patch("claude_memory.embedding.EmbeddingService") as mock_embedder_cls:
        mock_embedding_service = mock_embedder_cls.return_value
        # Mock encoding logic
        mock_embedding_service.encode.return_value = [0.1] * 1024

        # Mock Vector Store
        mock_vector_store = MagicMock()
        mock_vector_store.upsert = AsyncMock()

        service = MemoryService(
            embedding_service=mock_embedding_service, vector_store=mock_vector_store
        )

        # Ensure our mock repo is what the service uses
        service.repo = mock_repo
        return service


@pytest.mark.asyncio
async def test_analyze_graph_pagerank(memory_service: Any, mock_repo: Any) -> None:
    """Test PageRank execution via Python-based compute_pagerank."""

    # Mock Cypher output for rank query
    # Logic in tools uses execute_cypher
    mock_node = MagicMock()
    mock_node.properties = {"name": "Important Node", "rank": 0.85}
    mock_node.labels = {"Entity", "Concept"}

    # execute_cypher returns an object with result_set
    mock_res = MagicMock()
    mock_res.result_set = [[mock_node]]
    mock_repo.execute_cypher.side_effect = [
        mock_res,  # MATCH (n:Entity) RETURN n
        MagicMock(result_set=[]),  # MATCH edges
    ]

    with patch(
        "claude_memory.analysis.compute_pagerank",
        return_value=[{"name": "Important Node", "rank": 0.85}],
    ):
        results = await memory_service.analyze_graph("pagerank")

    assert len(results) == 1
    assert results[0]["name"] == "Important Node"

    # Verify execute_cypher was called for node fetch
    assert mock_repo.execute_cypher.call_count >= 1


@pytest.mark.asyncio
async def test_consolidate_memories(memory_service: Any, mock_repo: Any) -> None:
    """Test consolidation workflow using Repository mocks."""

    # Setup mocks
    mock_repo.create_node.return_value = {"id": "generated-uuid", "name": "Consolidated Memory"}

    # Patch UUID to return a fixed ID for the logic inside the method
    with patch("uuid.uuid4", return_value="generated-uuid"):
        result = await memory_service.consolidate_memories(["id-1", "id-2"], "Summary text")

    # Result comes from create_node return value (the mock)
    assert result["id"] == "generated-uuid"

    # Verify create_node called (Logic)
    mock_repo.create_node.assert_called_once()
    args = mock_repo.create_node.call_args
    assert args[0][0] == "Concept"  # Label
    # assert args[0][2] is not None  # Embedding provided - NO LONGER TRUE

    # Verify Vector Upsert
    memory_service.vector_store.upsert.assert_called_once()
    upsert_args = memory_service.vector_store.upsert.call_args
    assert upsert_args.kwargs["id"] == "generated-uuid"
    assert len(upsert_args.kwargs["vector"]) == 1024

    # Verify create_edge called for links (Data Access)
    assert mock_repo.create_edge.call_count == 2

    # Verify first link
    call1 = mock_repo.create_edge.call_args_list[0]
    # args: (from, to, type, props)
    assert call1[0][0] == "id-1"
    # The METHOD uses the generated UUID for the edge target, NOT the create_node return value
    assert call1[0][1] == "generated-uuid"
    assert call1[0][2] == "PART_OF"

    # Verify archive called
    assert mock_repo.update_node.call_count == 2
    assert mock_repo.update_node.call_args_list[0][0][1]["status"] == "archived"
