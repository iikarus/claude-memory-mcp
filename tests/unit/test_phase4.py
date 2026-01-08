from unittest.mock import MagicMock, patch

import pytest

from claude_memory.tools import MemoryService


@pytest.fixture
def mock_repo():
    with patch("claude_memory.tools.MemoryRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        # Default returns
        repo_instance.create_node.return_value = {"id": "mock-id", "name": "Mock Node"}
        repo_instance.create_edge.return_value = {"id": "mock-rel-id"}
        repo_instance.update_node.return_value = {"id": "mock-id"}
        repo_instance.execute_cypher.return_value = MagicMock(result_set=[])
        yield repo_instance


@pytest.fixture
def memory_service(mock_repo):
    # Initialize service; it typically instantiates Repo, but we patched the class
    service = MemoryService()
    # Mock encoder to avoid downloading hefty models
    service._get_encoder = MagicMock()
    service._get_encoder.return_value.encode.return_value.tolist.return_value = [0.1] * 1024

    # Ensure our mock instance is what the service holds
    service.repo = mock_repo  # Explicit injection for safety in test
    return service


@pytest.mark.asyncio
async def test_analyze_graph_pagerank(memory_service, mock_repo):
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

    # Verify execute_cypher was called with PageRank algo
    # First call is the CALL algo..., second is MATCH ...
    # We can check specific calls
    assert mock_repo.execute_cypher.call_count >= 1
    found_algo = False
    for call in mock_repo.execute_cypher.call_args_list:
        if "algo.pageRank" in call[0][0]:
            found_algo = True
    assert found_algo


@pytest.mark.asyncio
async def test_consolidate_memories(memory_service, mock_repo):
    """Test consolidation workflow using Repository mocks."""

    # Setup mocks
    mock_repo.create_node.return_value = {"id": "new-id", "name": "Consolidated Memory"}

    # Patch UUID to return a fixed ID for the logic inside the method
    with patch("uuid.uuid4", return_value="generated-uuid"):
        result = await memory_service.consolidate_memories(["id-1", "id-2"], "Summary text")

    # Result comes from create_node return value (the mock)
    assert result["id"] == "new-id"

    # Verify create_node called (Logic)
    mock_repo.create_node.assert_called_once()
    args = mock_repo.create_node.call_args
    assert args[0][0] == "Concept"  # Label
    assert args[0][2] is not None  # Embedding provided

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
