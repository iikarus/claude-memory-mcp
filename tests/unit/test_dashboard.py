"""Tests for dashboard/app.py utility functions.

Imports dashboard.app per-test to avoid module-scope sys.modules contamination
that kills coverage instrumentation for claude_memory.* in subsequent tests.
"""

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch


def _import_app() -> Any:
    """Import dashboard.app with all heavy deps mocked, safe for coverage."""
    mock_st = MagicMock()
    mock_st.cache_resource = lambda func: func  # Identity decorator

    with patch.dict(os.environ, {"EMBEDDING_API_URL": "http://mock-api"}):
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
            # Force reimport so we get a fresh module
            if "dashboard.app" in sys.modules:
                del sys.modules["dashboard.app"]
            from dashboard import app

            return app


def test_get_stats() -> None:
    """Test retrieval of node and edge counts."""
    app = _import_app()

    mock_service = MagicMock()
    mock_service.repo.execute_cypher.side_effect = [
        MagicMock(result_set=[[42]]),  # Nodes
        MagicMock(result_set=[[10]]),  # Edges
    ]

    with patch.object(app, "get_service", return_value=mock_service):
        nodes, edges = app.get_stats()

    assert nodes == 42
    assert edges == 10
    assert mock_service.repo.execute_cypher.call_count == 2


def test_get_graph_data() -> None:
    """Test graph data retrieval."""
    app = _import_app()

    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.result_set = []
    mock_service.repo.execute_cypher.return_value = mock_result

    with patch.object(app, "get_service", return_value=mock_service):
        app.get_graph_data(limit=50)

    # Check if cypher query was correct
    args = mock_service.repo.execute_cypher.call_args
    query = args[0][0]
    params = args[0][1]
    assert "OPTIONAL MATCH (n)-[r]->(m:Entity)" in query
    assert "LIMIT $limit" in query
    assert params["limit"] == 50
