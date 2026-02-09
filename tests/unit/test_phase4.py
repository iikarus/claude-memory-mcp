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
    """Test PageRank execution and result parsing."""

    # Mock Cypher output for rank query
    # Logic in tools uses execute_cypher
    mock_node = MagicMock()
    mock_node.properties = {"name": "Important Node", "rank": 0.85}
    mock_node.labels = {"Entity", "Concept"}

    # execute_cypher returns an object with result_set
    mock_res = MagicMock()
    mock_res.result_set = [[mock_node]]
    mock_repo.execute_cypher.return_value = mock_res

    results = await memory_service.analyze_graph("pagerank")

    assert len(results) == 1
    assert results[0]["name"] == "Important Node"


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

    # Verify vector upsert side-effect occurred
    memory_service.vector_store.upsert.assert_called_once()
    upsert_args = memory_service.vector_store.upsert.call_args
    assert upsert_args.kwargs["id"] == "generated-uuid"
    assert len(upsert_args.kwargs["vector"]) == 1024
