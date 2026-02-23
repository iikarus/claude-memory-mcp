"""Tests for MemoryRepository (repository.py).

Covers all uncovered lines: ensure_indices, create_node, get_node (null case),
update_node (empty result), delete_node (soft/hard), create_edge (empty result),
delete_edge, execute_cypher, get_subgraph (depth>0 paths), get_all_nodes,
get_total_node_count.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ─── Test Constants ─────────────────────────────────────────────────

NODE_ID = "node-001"
NODE_LABEL = "Concept"
NODE_NAME = "TestEntity"
PROJECT_ID = "project-alpha"
UPDATE_PROPS = {"version": "2.0"}
DELETE_REASON = "deprecated"

EDGE_FROM_ID = "node-001"
EDGE_TO_ID = "node-002"
EDGE_TYPE = "RELATED_TO"
EDGE_ID = "edge-001"
EDGE_PROPS: dict[str, Any] = {"confidence": 0.95}

CYPHER_QUERY = "MATCH (n) RETURN n"
CYPHER_PARAMS: dict[str, Any] = {"id": NODE_ID}

GRAPH_NAME = "claude_memory"
SUBGRAPH_DEPTH = 2
SUBGRAPH_IDS = ["node-001", "node-002"]
ALL_NODES_LIMIT = 1000


# ─── Mock Helpers ───────────────────────────────────────────────────


def _make_mock_node(properties: dict[str, Any]) -> MagicMock:
    """Creates a mock FalkorDB node with the given properties."""
    node = MagicMock()
    node.properties = properties
    node.labels = [NODE_LABEL, "Entity"]
    return node


def _make_mock_edge(properties: dict[str, Any]) -> MagicMock:
    """Creates a mock FalkorDB edge with the given properties."""
    edge = MagicMock()
    edge.properties = properties
    return edge


def _make_mock_result(rows: list[list[Any]]) -> MagicMock:
    """Creates a mock FalkorDB query result."""
    result = MagicMock()
    result.result_set = rows
    return result


# ─── Module Import ──────────────────────────────────────────────────


@pytest.fixture()
def mock_graph() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def repo(mock_graph: MagicMock) -> Any:
    with patch("claude_memory.repository.FalkorDB") as mock_falkordb:
        mock_client = MagicMock()
        mock_client.select_graph.return_value = mock_graph
        mock_falkordb.return_value = mock_client

        from claude_memory.repository import MemoryRepository

        r = MemoryRepository()
        return r


# ─── ensure_indices Tests ───────────────────────────────────────────


def test_ensure_indices_is_noop(repo: Any) -> None:
    """ensure_indices is currently a no-op pass statement."""
    repo.ensure_indices()  # Should not raise


# ─── create_node Tests ──────────────────────────────────────────────


def test_create_node(repo: Any, mock_graph: MagicMock) -> None:
    node_props = {
        "name": NODE_NAME,
        "project_id": PROJECT_ID,
        "updated_at": "2024-01-01T00:00:00Z",
    }
    mock_node = _make_mock_node(node_props)
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.create_node(NODE_LABEL, node_props)
    assert result == node_props
    mock_graph.query.assert_called_once()


# ─── get_node Tests ─────────────────────────────────────────────────


def test_get_node_found(repo: Any, mock_graph: MagicMock) -> None:
    node_props = {"id": NODE_ID, "name": NODE_NAME}
    mock_node = _make_mock_node(node_props)
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.get_node(NODE_ID)
    assert result == node_props


def test_get_node_not_found(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.get_node(NODE_ID)
    assert result is None


# ─── update_node Tests ──────────────────────────────────────────────


def test_update_node_success(repo: Any, mock_graph: MagicMock) -> None:
    updated_props = {"id": NODE_ID, **UPDATE_PROPS}
    mock_node = _make_mock_node(updated_props)
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.update_node(NODE_ID, UPDATE_PROPS)
    assert result == updated_props


def test_update_node_not_found(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.update_node(NODE_ID, UPDATE_PROPS)
    assert result == {}


# ─── delete_node Tests ──────────────────────────────────────────────


def test_delete_node_hard(repo: Any, mock_graph: MagicMock) -> None:
    result = repo.delete_node(NODE_ID)
    assert result is True
    mock_graph.query.assert_called_once()


def test_delete_node_soft(repo: Any, mock_graph: MagicMock) -> None:
    mock_node = _make_mock_node({"id": NODE_ID, "deleted": True})
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.delete_node(NODE_ID, soft_delete=True, reason=DELETE_REASON)
    assert result is True


def test_delete_node_soft_not_found(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.delete_node(NODE_ID, soft_delete=True, reason=DELETE_REASON)
    assert result is False


# ─── create_edge Tests ──────────────────────────────────────────────


def test_create_edge_success(repo: Any, mock_graph: MagicMock) -> None:
    mock_edge = _make_mock_edge(EDGE_PROPS)
    mock_graph.query.return_value = _make_mock_result([[mock_edge]])

    result = repo.create_edge(EDGE_FROM_ID, EDGE_TO_ID, EDGE_TYPE, EDGE_PROPS)
    assert result == EDGE_PROPS


def test_create_edge_nodes_not_found(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.create_edge(EDGE_FROM_ID, EDGE_TO_ID, EDGE_TYPE, EDGE_PROPS)
    assert result == {}


# ─── delete_edge Tests ──────────────────────────────────────────────


def test_delete_edge(repo: Any, mock_graph: MagicMock) -> None:
    result = repo.delete_edge(EDGE_ID)
    assert result is True
    mock_graph.query.assert_called_once()


# ─── execute_cypher Tests ───────────────────────────────────────────


def test_execute_cypher_with_params(repo: Any, mock_graph: MagicMock) -> None:
    expected = _make_mock_result([["result"]])
    mock_graph.query.return_value = expected

    result = repo.execute_cypher(CYPHER_QUERY, CYPHER_PARAMS)
    assert result is expected
    mock_graph.query.assert_called_once_with(CYPHER_QUERY, CYPHER_PARAMS)


def test_execute_cypher_without_params(repo: Any, mock_graph: MagicMock) -> None:
    expected = _make_mock_result([["result"]])
    mock_graph.query.return_value = expected

    result = repo.execute_cypher(CYPHER_QUERY)
    assert result is expected
    mock_graph.query.assert_called_once_with(CYPHER_QUERY, {})


# ─── get_subgraph Tests ────────────────────────────────────────────


def test_get_subgraph_empty_ids(repo: Any) -> None:
    result = repo.get_subgraph([])
    assert result == {"nodes": [], "edges": []}


def test_get_subgraph_depth_zero(repo: Any, mock_graph: MagicMock) -> None:
    """depth=0 uses the simpler MATCH query without UNWIND."""
    node_data = [
        {"id": NODE_ID, "properties": {"id": NODE_ID, "name": NODE_NAME}},
    ]
    mock_graph.query.return_value = _make_mock_result([[node_data]])

    result = repo.get_subgraph([NODE_ID], depth=0)
    assert len(result["nodes"]) == 1
    assert result["edges"] == []
    assert result["nodes"][0]["id"] == NODE_ID


def test_get_subgraph_depth_zero_empty(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.get_subgraph([NODE_ID], depth=0)
    assert result == {"nodes": [], "edges": []}


def test_get_subgraph_with_depth(repo: Any, mock_graph: MagicMock) -> None:
    """depth>0 uses UNWIND on relationships, returns deduplicated nodes/edges."""
    edge_data = [
        {"id": EDGE_ID, "source": EDGE_FROM_ID, "target": EDGE_TO_ID, "type": EDGE_TYPE},
    ]
    node_data = [
        {"id": EDGE_FROM_ID, "properties": {"id": EDGE_FROM_ID, "name": "NodeA"}},
        {"id": EDGE_TO_ID, "properties": {"id": EDGE_TO_ID, "name": "NodeB"}},
    ]
    mock_graph.query.return_value = _make_mock_result([[edge_data, node_data]])

    result = repo.get_subgraph(SUBGRAPH_IDS, depth=SUBGRAPH_DEPTH)
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1


def test_get_subgraph_with_depth_empty_result(repo: Any, mock_graph: MagicMock) -> None:
    """When depth>0 UNWIND returns empty, fallback to isolated node query."""
    # First call (UNWIND query) returns empty
    # Second call (fallback node query) returns nodes
    node_data = [
        {"id": NODE_ID, "properties": {"id": NODE_ID, "name": NODE_NAME}},
    ]
    mock_graph.query.side_effect = [
        _make_mock_result([]),  # UNWIND query empty
        _make_mock_result([[node_data]]),  # fallback query
    ]

    result = repo.get_subgraph([NODE_ID], depth=SUBGRAPH_DEPTH)
    assert len(result["nodes"]) == 1


def test_get_subgraph_with_depth_completely_empty(repo: Any, mock_graph: MagicMock) -> None:
    """Both UNWIND and fallback queries return empty."""
    mock_graph.query.side_effect = [
        _make_mock_result([]),  # UNWIND query empty
        _make_mock_result([]),  # fallback also empty
    ]

    result = repo.get_subgraph([NODE_ID], depth=SUBGRAPH_DEPTH)
    assert result == {"nodes": [], "edges": []}


# ─── get_all_nodes Tests ───────────────────────────────────────────


def test_get_all_nodes(repo: Any, mock_graph: MagicMock) -> None:
    node_props = {"id": NODE_ID, "name": NODE_NAME, "embedding": MOCK_VECTOR}
    mock_node = _make_mock_node(node_props)
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.get_all_nodes(limit=ALL_NODES_LIMIT)
    assert len(result) == 1
    assert result[0]["id"] == NODE_ID


# ─── get_total_node_count Tests ─────────────────────────────────────


MOCK_VECTOR = [0.1, 0.2, 0.3]


def test_get_total_node_count(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([[42]])

    result = repo.get_total_node_count()
    assert result == 42


def test_get_total_node_count_empty(repo: Any, mock_graph: MagicMock) -> None:
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.get_total_node_count()
    assert result == 0


# ─── query_timeline Tests ──────────────────────────────────────────


def test_query_timeline_no_project(repo: Any, mock_graph: MagicMock) -> None:
    """query_timeline returns entities without project filter."""
    mock_node = _make_mock_node(
        {"id": NODE_ID, "name": NODE_NAME, "occurred_at": "2026-01-15T12:00:00"}
    )
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.query_timeline(start="2026-01-01", end="2026-02-01")
    assert len(result) == 1
    assert result[0]["id"] == NODE_ID
    # Verify no project_id in query params
    call_args = mock_graph.query.call_args
    assert "project_id" not in call_args[0][1]


def test_query_timeline_with_project(repo: Any, mock_graph: MagicMock) -> None:
    """query_timeline filters by project_id when provided."""
    mock_node = _make_mock_node({"id": NODE_ID, "name": NODE_NAME, "project_id": PROJECT_ID})
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.query_timeline(start="2026-01-01", end="2026-02-01", project_id=PROJECT_ID)
    assert len(result) == 1
    call_args = mock_graph.query.call_args
    assert call_args[0][1]["project_id"] == PROJECT_ID


def test_query_timeline_empty(repo: Any, mock_graph: MagicMock) -> None:
    """query_timeline returns empty list when no matches."""
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.query_timeline(start="2026-01-01", end="2026-02-01")
    assert result == []


# ─── get_temporal_neighbors Tests ──────────────────────────────────


def test_get_temporal_neighbors_before(repo: Any, mock_graph: MagicMock) -> None:
    """get_temporal_neighbors direction=before returns predecessors."""
    mock_node = _make_mock_node({"id": "prev-1", "name": "Previous"})
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.get_temporal_neighbors(NODE_ID, direction="before")
    assert len(result) == 1
    assert result[0]["id"] == "prev-1"
    query_str = mock_graph.query.call_args[0][0]
    assert "<-[r:" in query_str


def test_get_temporal_neighbors_after(repo: Any, mock_graph: MagicMock) -> None:
    """get_temporal_neighbors direction=after returns successors."""
    mock_node = _make_mock_node({"id": "next-1", "name": "Next"})
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.get_temporal_neighbors(NODE_ID, direction="after")
    assert len(result) == 1
    query_str = mock_graph.query.call_args[0][0]
    assert "->(m:Entity)" in query_str


def test_get_temporal_neighbors_both(repo: Any, mock_graph: MagicMock) -> None:
    """get_temporal_neighbors default direction returns both."""
    m1 = _make_mock_node({"id": "prev-1"})
    m2 = _make_mock_node({"id": "next-1"})
    mock_graph.query.return_value = _make_mock_result([[m1], [m2]])

    result = repo.get_temporal_neighbors(NODE_ID)
    assert len(result) == 2
    query_str = mock_graph.query.call_args[0][0]
    assert "DISTINCT m" in query_str


# ─── create_temporal_edge Tests ────────────────────────────────────


def test_create_temporal_edge_success(repo: Any, mock_graph: MagicMock) -> None:
    """create_temporal_edge creates edge and returns metadata."""
    mock_graph.query.return_value = _make_mock_result([["PRECEDED_BY", "entity-a", "entity-b"]])

    result = repo.create_temporal_edge("entity-a", "entity-b")
    assert result["rel_type"] == "PRECEDED_BY"
    assert result["from_id"] == "entity-a"
    assert result["to_id"] == "entity-b"


def test_create_temporal_edge_not_found(repo: Any, mock_graph: MagicMock) -> None:
    """create_temporal_edge returns error when entities not found."""
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.create_temporal_edge("missing-a", "missing-b")
    assert "error" in result


def test_create_temporal_edge_with_properties(repo: Any, mock_graph: MagicMock) -> None:
    """create_temporal_edge passes custom properties to the edge."""
    mock_graph.query.return_value = _make_mock_result([["CONCURRENT_WITH", "a", "b"]])
    custom_props = {"reason": "same session", "created_at": "2026-01-15"}

    result = repo.create_temporal_edge(
        "a", "b", edge_type="CONCURRENT_WITH", properties=custom_props
    )
    assert result["rel_type"] == "CONCURRENT_WITH"
    # Verify the original props dict wasn't mutated
    assert custom_props == {"reason": "same session", "created_at": "2026-01-15"}


# ─── Salience / increment_salience Tests ────────────────────────────


def test_increment_salience_empty_ids(repo: Any, mock_graph: MagicMock) -> None:
    """increment_salience returns [] immediately for empty list."""
    result = repo.increment_salience([])
    assert result == []
    mock_graph.query.assert_not_called()


def test_increment_salience_returns_updated_scores(repo: Any, mock_graph: MagicMock) -> None:
    """increment_salience queries Cypher and maps rows to dicts."""
    mock_graph.query.return_value = _make_mock_result(
        [["entity-1", 2.0, 2], ["entity-2", 1.585, 1]]
    )
    result = repo.increment_salience(["entity-1", "entity-2"])
    assert len(result) == 2
    assert result[0] == {"id": "entity-1", "salience_score": 2.0, "retrieval_count": 2}
    assert result[1]["id"] == "entity-2"
    # Verify query was called with the node IDs
    call_params = mock_graph.query.call_args[0][1]
    assert call_params["ids"] == ["entity-1", "entity-2"]


# ─── get_most_recent_entity Tests ───────────────────────────────────


def test_get_most_recent_entity_found(repo: Any, mock_graph: MagicMock) -> None:
    """Returns the most recent entity dict when found."""
    node_props = {"id": "entity-1", "name": "Recent", "project_id": "proj-1"}
    mock_node = _make_mock_node(node_props)
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.get_most_recent_entity("proj-1")
    assert result == node_props
    call_params = mock_graph.query.call_args[0][1]
    assert call_params["pid"] == "proj-1"


def test_get_most_recent_entity_not_found(repo: Any, mock_graph: MagicMock) -> None:
    """Returns None when no entities exist in project."""
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.get_most_recent_entity("empty-project")
    assert result is None


# ─── get_bottles Tests ──────────────────────────────────────────────


def test_get_bottles_basic(repo: Any, mock_graph: MagicMock) -> None:
    """get_bottles returns Bottle entities ordered by date DESC."""
    node_props = {"id": "bottle-1", "name": "Remember this", "node_type": "Bottle"}
    mock_node = _make_mock_node(node_props)
    mock_graph.query.return_value = _make_mock_result([[mock_node]])

    result = repo.get_bottles(limit=5)
    assert len(result) == 1
    assert result[0]["id"] == "bottle-1"
    # Verify query used correct params
    call_params = mock_graph.query.call_args[0][1]
    assert call_params["limit"] == 5


def test_get_bottles_with_text_filter(repo: Any, mock_graph: MagicMock) -> None:
    """get_bottles adds CONTAINS filter when search_text provided."""
    mock_graph.query.return_value = _make_mock_result([])

    repo.get_bottles(search_text="important")
    call_query = mock_graph.query.call_args[0][0]
    assert "CONTAINS" in call_query
    call_params = mock_graph.query.call_args[0][1]
    assert call_params["text"] == "important"


def test_get_bottles_empty(repo: Any, mock_graph: MagicMock) -> None:
    """get_bottles returns empty list when no bottles exist."""
    mock_graph.query.return_value = _make_mock_result([])

    result = repo.get_bottles()
    assert result == []


# ─── Phase 15A: Graph Health Metrics Tests ──────────────────────────


def test_get_graph_health_empty_graph(repo: Any, mock_graph: MagicMock) -> None:
    """get_graph_health returns zeros for an empty graph."""
    mock_graph.query.return_value = _make_mock_result([[0]])

    result = repo.get_graph_health()
    assert result["total_nodes"] == 0
    assert result["total_edges"] == 0
    assert result["orphan_count"] == 0
    assert result["density"] == 0.0
    assert result["avg_degree"] == 0.0


def test_get_graph_health_single_orphan(repo: Any, mock_graph: MagicMock) -> None:
    """Single node with no edges is an orphan."""
    # total=1, entity=1, observation=0, edges=0, orphans=1
    mock_graph.query.side_effect = [
        _make_mock_result([[1]]),
        _make_mock_result([[1]]),
        _make_mock_result([[0]]),
        _make_mock_result([[0]]),
        _make_mock_result([[1]]),
    ]

    result = repo.get_graph_health()
    assert result["total_nodes"] == 1
    assert result["entity_count"] == 1
    assert result["observation_count"] == 0
    assert result["total_edges"] == 0
    assert result["orphan_count"] == 1
    assert result["density"] == 0.0
    assert result["avg_degree"] == 0.0


def test_get_graph_health_with_edges(repo: Any, mock_graph: MagicMock) -> None:
    """Graph with nodes and edges computes correct density and avg_degree."""
    # total=5, entity=3, observation=2, edges=4, orphans=0
    mock_graph.query.side_effect = [
        _make_mock_result([[5]]),
        _make_mock_result([[3]]),
        _make_mock_result([[2]]),
        _make_mock_result([[4]]),
        _make_mock_result([[0]]),
    ]

    result = repo.get_graph_health()
    assert result["total_nodes"] == 5
    assert result["entity_count"] == 3
    assert result["observation_count"] == 2
    assert result["total_edges"] == 4
    assert result["orphan_count"] == 0
    # density = 4 / (5*4) = 0.2
    assert result["density"] == 0.2
    # avg_degree = 4 / 5 = 0.8
    assert result["avg_degree"] == 0.8


def test_get_all_edges(repo: Any, mock_graph: MagicMock) -> None:
    """get_all_edges returns structured edge list."""
    mock_graph.query.return_value = _make_mock_result(
        [
            ["n1", "n2", "RELATED_TO"],
            ["n2", "n3", "DEPENDS_ON"],
        ]
    )

    result = repo.get_all_edges()
    assert len(result) == 2
    assert result[0] == {"source": "n1", "target": "n2", "type": "RELATED_TO"}
    assert result[1] == {"source": "n2", "target": "n3", "type": "DEPENDS_ON"}


# ─── Constructor Retry Tests ────────────────────────────────────────


def test_constructor_retries_on_connection_error() -> None:
    """FalkorDB() failing twice then succeeding should yield a working repo."""
    mock_client = MagicMock()

    with (
        patch("claude_memory.repository.FalkorDB") as mock_fdb,
        patch("claude_memory.repository.time.sleep") as mock_sleep,
    ):
        mock_fdb.side_effect = [ConnectionError("refused"), ConnectionError("refused"), mock_client]

        from claude_memory.repository import MemoryRepository

        r = MemoryRepository()

    assert r.client is mock_client
    assert mock_fdb.call_count == 3
    assert mock_sleep.call_count == 2


def test_constructor_raises_after_max_retries() -> None:
    """FalkorDB() failing on all attempts should raise ConnectionError."""
    with (
        patch("claude_memory.repository.FalkorDB") as mock_fdb,
        patch("claude_memory.repository.time.sleep"),
    ):
        mock_fdb.side_effect = ConnectionError("refused")

        from claude_memory.repository import MemoryRepository

        with pytest.raises(ConnectionError, match="refused"):
            MemoryRepository()
