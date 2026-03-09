"""Tests for the Streamlit dashboard (dashboard/app.py).

Tests async helpers and the main function.
Heavy Streamlit/PyVis UI logic is tested via function-level mocking.
"""

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ─── Test Constants ─────────────────────────────────────────────────

NODE_COUNT = 42
EDGE_COUNT = 17
GRAPH_LIMIT_DEFAULT = 100
GRAPH_LIMIT_CUSTOM = 50
FOCUS_NODE_NAME = "Python"
SEARCH_QUERY = "async patterns"
STALE_DAYS = 30

MOCK_NODE_ID = "node-001"
MOCK_NODE_NAME = "TestEntity"
MOCK_EDGE_RELATION = "RELATED_TO"

SHUTDOWN_TAG_PREFIX = "shutdown_"
BACKUP_SCRIPT_PATH = "scripts/backup_restore.py"

MOCK_SEARCH_RESULT_SCORE = 0.85


# ─── Module Import ──────────────────────────────────────────────────

# Streamlit and PyVis must be mocked before import
mock_st = MagicMock()
mock_components = MagicMock()
mock_network = MagicMock()


@pytest.fixture(autouse=True)
def _patch_dashboard_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch all heavy dashboard dependencies before test execution."""
    monkeypatch.setitem(sys.modules, "streamlit", mock_st)
    monkeypatch.setitem(sys.modules, "streamlit.components", MagicMock())
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", mock_components)
    monkeypatch.setitem(sys.modules, "pyvis", MagicMock())
    monkeypatch.setitem(sys.modules, "pyvis.network", MagicMock())


# We need to test the async utility functions directly
# Import them with all deps mocked via the fixture


def _import_dashboard() -> Any:
    """Dynamically import dashboard.app with mocking in place."""
    with patch.dict(os.environ, {"EMBEDDING_API_URL": "http://mock-api"}):
        with patch("claude_memory.embedding.EmbeddingService"):
            with patch("claude_memory.repository.FalkorDB"):
                with patch("claude_memory.lock_manager.redis.Redis"):
                    # Force reimport
                    if "dashboard.app" in sys.modules:
                        del sys.modules["dashboard.app"]
                    from dashboard import app as dashboard_app

                    return dashboard_app


# ─── get_stats Tests ────────────────────────────────────────────────


async def test_get_stats() -> None:
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_result_nodes = MagicMock()
    mock_result_nodes.result_set = [[NODE_COUNT]]
    mock_result_edges = MagicMock()
    mock_result_edges.result_set = [[EDGE_COUNT]]
    mock_service.repo.execute_cypher.side_effect = [mock_result_nodes, mock_result_edges]

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        nodes, edges = dashboard_app.get_stats()

    assert nodes == NODE_COUNT
    assert edges == EDGE_COUNT


# ─── get_graph_data Tests ───────────────────────────────────────────


def test_get_graph_data_global() -> None:
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_service.repo.execute_cypher.return_value = mock_result

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        result = dashboard_app.get_graph_data(limit=GRAPH_LIMIT_DEFAULT)

    mock_service.repo.execute_cypher.assert_called_once()
    query_used = mock_service.repo.execute_cypher.call_args[0][0]
    assert "MATCH (n:Entity)" in query_used
    assert result is mock_result


def test_get_graph_data_focused() -> None:
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_service.repo.execute_cypher.return_value = mock_result

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        result = dashboard_app.get_graph_data(limit=GRAPH_LIMIT_CUSTOM, focus=FOCUS_NODE_NAME)

    query_used = mock_service.repo.execute_cypher.call_args[0][0]
    assert "$focus" in query_used
    # Verify focus was passed as a parameter
    params_used = mock_service.repo.execute_cypher.call_args[0][1]
    assert params_used["focus"] == FOCUS_NODE_NAME
    assert result is mock_result


# ─── main() Tests ───────────────────────────────────────────────────


def test_main_explorer_mode() -> None:
    """Test main() with Explorer menu + Refresh Graph button click (lines 78-106)."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    # execute_cypher is called 3 times: nodes count, edges count, graph data
    mock_edge_stats = MagicMock()
    mock_edge_stats.result_set = [[EDGE_COUNT]]

    # Build mock graph result with nodes, relationship, and neighbor
    mock_node_n = MagicMock()
    mock_node_n.properties = {"id": MOCK_NODE_ID, "name": MOCK_NODE_NAME}
    mock_rel = MagicMock()
    mock_rel.relation = MOCK_EDGE_RELATION
    mock_node_m = MagicMock()
    mock_node_m.properties = {"id": "node-002", "name": "Neighbor"}
    mock_graph_result = MagicMock()
    # Include BOTH a connected row (n, rel, m) AND a standalone row (n, None, None)
    mock_standalone = MagicMock()
    mock_standalone.properties = {"id": "node-003", "name": "Standalone"}
    mock_graph_result.result_set = [
        [mock_node_n, mock_rel, mock_node_m],
        [mock_standalone, None, None],
    ]

    mock_service.repo.execute_cypher.side_effect = [
        mock_stats_result,  # get_stats: node count
        mock_edge_stats,  # get_stats: edge count
        mock_graph_result,  # get_graph_data: graph cypher result
    ]

    # Mock Streamlit widgets
    mock_st.sidebar.radio.return_value = "Explorer"
    mock_st.sidebar.button.return_value = False
    mock_st.button.return_value = True  # "Refresh Graph" clicked clicked
    mock_st.slider.return_value = GRAPH_LIMIT_DEFAULT
    mock_st.text_input.return_value = ""
    mock_st.columns.return_value = [MagicMock(), MagicMock()]

    mock_network_instance = MagicMock()

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = None  # asyncio.run not used in Explorer tab
            with patch.object(dashboard_app, "Network", return_value=mock_network_instance):
                with patch("builtins.open", MagicMock()):
                    dashboard_app.main()

    mock_st.title.assert_called()
    mock_network_instance.add_node.assert_called()
    mock_network_instance.add_edge.assert_called()


def test_main_search_mode_no_query() -> None:
    """Test main() with Search menu, empty query."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Search"
    mock_st.sidebar.button.return_value = False
    mock_st.text_input.return_value = ""

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = (NODE_COUNT, EDGE_COUNT)
            dashboard_app.main()


def test_main_search_mode_with_query() -> None:
    """Test main() with Search menu and query text."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_search_result = MagicMock()
    mock_search_result.name = MOCK_NODE_NAME
    mock_search_result.score = MOCK_SEARCH_RESULT_SCORE

    mock_st.sidebar.radio.return_value = "Search"
    mock_st.sidebar.button.return_value = False
    mock_st.text_input.return_value = SEARCH_QUERY

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run") as mock_async_run:
            # asyncio.run is only called for service.search (get_stats is sync)
            mock_async_run.return_value = [mock_search_result]
            dashboard_app.main()


def test_main_maintenance_mode() -> None:
    """Test main() with Maintenance menu (lines 117-125)."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Maintenance"
    mock_st.sidebar.button.return_value = False
    mock_st.button.return_value = False
    mock_st.number_input.return_value = STALE_DAYS

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = (NODE_COUNT, EDGE_COUNT)
            dashboard_app.main()


def test_main_maintenance_scan() -> None:
    """Test maintenance scan button click."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Maintenance"
    mock_st.sidebar.button.return_value = False
    mock_st.button.return_value = True  # "Scan" button clicked
    mock_st.number_input.return_value = STALE_DAYS

    stale_entities = [{"id": MOCK_NODE_ID, "name": MOCK_NODE_NAME}]

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run") as mock_run:
            mock_run.side_effect = [
                (NODE_COUNT, EDGE_COUNT),
                stale_entities,
            ]
            dashboard_app.main()


def test_main_shutdown_backup_success() -> None:
    """Test safe shutdown with successful backup."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Explorer"
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock()]

    # Sidebar button for shutdown
    mock_st.sidebar.button.side_effect = [True]  # "Safe Shutdown" clicked

    mock_status_ctx = MagicMock()
    mock_st.sidebar.status.return_value.__enter__ = MagicMock(return_value=mock_status_ctx)
    mock_st.sidebar.status.return_value.__exit__ = MagicMock(return_value=False)

    mock_backup_result = MagicMock()
    mock_backup_result.returncode = 0

    mock_docker_result = MagicMock()
    mock_docker_result.stdout = f"{MOCK_NODE_ID}\n"

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run", side_effect=lambda coro: (NODE_COUNT, EDGE_COUNT)):
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.side_effect = [mock_backup_result, mock_docker_result, MagicMock()]
                dashboard_app.main()


def test_main_shutdown_backup_failure() -> None:
    """Test safe shutdown that aborts when backup fails."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Explorer"
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.sidebar.button.side_effect = [True]

    mock_status_ctx = MagicMock()
    mock_st.sidebar.status.return_value.__enter__ = MagicMock(return_value=mock_status_ctx)
    mock_st.sidebar.status.return_value.__exit__ = MagicMock(return_value=False)

    mock_backup_result = MagicMock()
    mock_backup_result.returncode = 1
    mock_backup_result.stderr = "disk full"

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run", side_effect=lambda coro: (NODE_COUNT, EDGE_COUNT)):
            with patch("subprocess.run", return_value=mock_backup_result):
                dashboard_app.main()

    mock_st.error.assert_called()


def test_main_shutdown_backup_exception() -> None:
    """Test safe shutdown when backup raises an exception."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Explorer"
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.sidebar.button.side_effect = [True]

    mock_status_ctx = MagicMock()
    mock_st.sidebar.status.return_value.__enter__ = MagicMock(return_value=mock_status_ctx)
    mock_st.sidebar.status.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run", side_effect=lambda coro: (NODE_COUNT, EDGE_COUNT)):
            with patch("subprocess.run", side_effect=FileNotFoundError("python not found")):
                dashboard_app.main()

    mock_st.error.assert_called()


def test_main_shutdown_no_containers() -> None:
    """Test shutdown when no docker containers are found."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Explorer"
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.sidebar.button.side_effect = [True]

    mock_status_ctx = MagicMock()
    mock_st.sidebar.status.return_value.__enter__ = MagicMock(return_value=mock_status_ctx)
    mock_st.sidebar.status.return_value.__exit__ = MagicMock(return_value=False)

    mock_backup_result = MagicMock()
    mock_backup_result.returncode = 0

    mock_docker_result = MagicMock()
    mock_docker_result.stdout = ""  # No containers

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run", side_effect=lambda coro: (NODE_COUNT, EDGE_COUNT)):
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.side_effect = [mock_backup_result, mock_docker_result]
                dashboard_app.main()


def test_main_shutdown_docker_exception() -> None:
    """Test shutdown when docker command raises."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "Explorer"
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.sidebar.button.side_effect = [True]

    mock_status_ctx = MagicMock()
    mock_st.sidebar.status.return_value.__enter__ = MagicMock(return_value=mock_status_ctx)
    mock_st.sidebar.status.return_value.__exit__ = MagicMock(return_value=False)

    mock_backup_result = MagicMock()
    mock_backup_result.returncode = 0

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run", side_effect=lambda coro: (NODE_COUNT, EDGE_COUNT)):
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.side_effect = [
                    mock_backup_result,
                    FileNotFoundError("docker not found"),
                ]
                dashboard_app.main()


def test_main_unknown_menu() -> None:
    """Branch 117→128: menu is not Explorer/Search/Maintenance → falls through."""
    dashboard_app = _import_dashboard()

    mock_service = MagicMock()
    mock_stats_result = MagicMock()
    mock_stats_result.result_set = [[NODE_COUNT]]
    mock_service.repo.execute_cypher.return_value = mock_stats_result

    mock_st.sidebar.radio.return_value = "UnknownMode"
    # Reset side_effect from previous test to prevent StopIteration
    mock_st.sidebar.button.side_effect = None
    mock_st.sidebar.button.return_value = False
    mock_st.button.return_value = False

    with patch.object(dashboard_app, "get_service", return_value=mock_service):
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = (NODE_COUNT, EDGE_COUNT)
            dashboard_app.main()
