import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Patch streamlit and backend modules before importing app
mock_st = MagicMock()
mock_st.cache_resource = lambda func: func  # Identity decorator

with patch.dict(
    sys.modules,
    {
        "streamlit": mock_st,
        "streamlit.components.v1": MagicMock(),
        "pyvis.network": MagicMock(),
        "claude_memory": MagicMock(),
        "claude_memory.tools": MagicMock(),
        "claude_memory.embedding": MagicMock(),
    },
):
    from dashboard import app


@pytest.fixture
def mock_service() -> Any:
    """Mock the MemoryService instance."""
    # Since we mocked claude_memory.tools in sys.modules, app.MemoryService is a MagicMock
    service_class_mock = app.MemoryService
    service_instance_mock = service_class_mock.return_value
    service_instance_mock.reset_mock(side_effect=True, return_value=True)
    yield service_instance_mock


@pytest.mark.asyncio
async def test_get_stats(mock_service: Any) -> None:
    """Test retrieval of node and edge counts."""
    # Setup mock returns structure: result_set[0][0]

    # Setup mock returns structure: result_set[0][0]
    mock_service.repo.execute_cypher.side_effect = [
        MagicMock(result_set=[[42]]),  # Nodes
        MagicMock(result_set=[[10]]),  # Edges
    ]

    nodes, edges = await app.get_stats()
    print(f"DEBUG: nodes={nodes}, edges={edges}")

    assert nodes == 42
    assert edges == 10
    assert mock_service.repo.execute_cypher.call_count == 2


@pytest.mark.asyncio
async def test_get_graph_data(mock_service: Any) -> None:
    """Test graph data retrieval."""
    mock_result = MagicMock()
    mock_result.result_set = []
    mock_service.repo.execute_cypher.return_value = mock_result

    await app.get_graph_data(limit=50)

    # Check if cypher query was correct
    args = mock_service.repo.execute_cypher.call_args
    query = args[0][0]
    assert "OPTIONAL MATCH (n)-[r]->(m:Entity)" in query
    assert "LIMIT 50" in query
