from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.schema import EntityDeleteParams, EntityUpdateParams, ObservationParams
from claude_memory.tools import MemoryService


@pytest.fixture  # type: ignore
def memory_service() -> Generator[MemoryService, None, None]:
    with patch("claude_memory.repository.FalkorDB"):
        service = MemoryService()
        # Mock the client and graph
        service.repo.client = MagicMock()
        service.repo.client.select_graph.return_value = MagicMock()
        yield service


@pytest.mark.asyncio  # type: ignore
async def test_update_entity_success(memory_service: MemoryService) -> None:
    # Setup mocks
    graph = memory_service.repo.client.select_graph.return_value
    # Mock return for the final update query
    mock_result_set = MagicMock()
    # Return a dummy node structure: [[Node(properties={...})]]
    mock_node = MagicMock()
    mock_node.properties = {"id": "123", "name": "Updated", "description": "New Desc"}
    mock_result_set.result_set = [[mock_node]]
    graph.query.return_value = mock_result_set

    params = EntityUpdateParams(entity_id="123", properties={"status": "inactive"})

    result = await memory_service.update_entity(params)

    assert result["id"] == "123"
    assert result["name"] == "Updated"

    # Verify query called with correct props
    args, kwargs = graph.query.call_args
    assert "SET n += $props" in args[0]
    # Check the params dict which is the second positional argument (index 1)
    params_dict = args[1]
    assert params_dict["props"]["status"] == "inactive"


@pytest.mark.asyncio  # type: ignore
async def test_soft_delete_entity(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value
    mock_node = MagicMock()
    mock_node.properties = {"id": "123", "deleted": True}
    graph.query.return_value.result_set = [[mock_node]]

    params = EntityDeleteParams(entity_id="123", reason="Duplicated", soft_delete=True)

    result = await memory_service.delete_entity(params)

    assert result["status"] == "soft_deleted"
    assert "SET n.deleted = true" in graph.query.call_args[0][0]


@pytest.mark.asyncio  # type: ignore
async def test_hard_delete_entity(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    params = EntityDeleteParams(entity_id="123", reason="Spam", soft_delete=False)

    result = await memory_service.delete_entity(params)

    assert result["status"] == "hard_deleted"
    assert "DETACH DELETE n" in graph.query.call_args[0][0]


@pytest.mark.asyncio  # type: ignore
async def test_add_observation(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    # Return the created observation node
    mock_node = MagicMock()
    mock_node.properties = {
        "id": "obs-789",
        "content": "User likes Python",
        "certainty": "confirmed",
    }
    graph.query.return_value.result_set = [[mock_node]]

    params = ObservationParams(
        entity_id="ent-123", content="User likes Python", certainty="confirmed"
    )

    with patch("uuid.uuid4", return_value="obs-789"):
        result = await memory_service.add_observation(params)

    assert result["id"] == "obs-789"
    assert result["content"] == "User likes Python"

    # Verify Cypher has both node creation and linking
    cypher = graph.query.call_args[0][0]
    assert "CREATE (o:Observation" in cypher
    assert "CREATE (e)-[:HAS_OBSERVATION]->(o)" in cypher
