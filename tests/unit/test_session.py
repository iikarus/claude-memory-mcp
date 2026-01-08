from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.schema import SessionEndParams, SessionStartParams
from claude_memory.tools import MemoryService


@pytest.fixture  # type: ignore
def memory_service() -> Generator[MemoryService, None, None]:
    with patch("claude_memory.repository.FalkorDB"):
        service = MemoryService()
        service.repo.client = MagicMock()
        service.repo.client.select_graph.return_value = MagicMock()
        yield service


@pytest.mark.asyncio  # type: ignore
async def test_start_session(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    mock_node = MagicMock()
    mock_node.properties = {
        "id": "sess-001",
        "project_id": "meta",
        "focus": "testing",
        "status": "active",
    }
    graph.query.return_value.result_set = [[mock_node]]

    params = SessionStartParams(project_id="meta", focus="testing")

    with patch("uuid.uuid4", return_value="sess-001"):
        result = await memory_service.start_session(params)

    assert result["id"] == "sess-001"
    assert result["status"] == "active"

    cypher = graph.query.call_args[0][0]
    assert "CREATE (s:Session)" in cypher
    assert "SET s = $props" in cypher

    # Check params
    call_params = graph.query.call_args[0][1]
    assert call_params["props"]["project_id"] == "meta"


@pytest.mark.asyncio  # type: ignore
async def test_end_session(memory_service: MemoryService) -> None:
    graph = memory_service.repo.client.select_graph.return_value

    mock_node = MagicMock()
    mock_node.properties = {"id": "sess-001", "status": "closed", "summary": "Done"}
    graph.query.return_value.result_set = [[mock_node]]

    params = SessionEndParams(session_id="sess-001", summary="Done", outcomes=["Great success"])

    result = await memory_service.end_session(params)

    assert result["status"] == "closed"
    assert result["summary"] == "Done"

    cypher = graph.query.call_args[0][0]
    assert "SET s.status = 'closed'" in cypher
    assert "SET s.summary = $summary" in cypher
