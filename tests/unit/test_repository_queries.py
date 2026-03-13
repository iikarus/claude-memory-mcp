"""Tests for repository_queries.py — coverage gap remediation.

3-evil/1-sad/1-happy per function for:
  - query_timeline
  - get_temporal_neighbors
  - create_temporal_edge
  - get_bottles
  - get_graph_health
  - list_orphans
  - get_all_edges
  - get_all_node_ids
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from claude_memory.repository_queries import RepositoryQueryMixin

# ─── Helpers ────────────────────────────────────────────────────────


def _make_mixin() -> RepositoryQueryMixin:
    """Create a RepositoryQueryMixin with a mocked select_graph."""
    mixin = RepositoryQueryMixin()
    mixin.select_graph = MagicMock()  # type: ignore[attr-defined]
    return mixin


def _mock_result(rows: list[list]) -> MagicMock:
    """Build a mock FalkorDB query result."""
    result = MagicMock()
    result.result_set = rows
    return result


def _entity_node(**props: object) -> SimpleNamespace:
    """Create a mock FalkorDB node with properties."""
    return SimpleNamespace(properties=props)


# ═══════════════════════════════════════════════════════════════
#  query_timeline
# ═══════════════════════════════════════════════════════════════


class TestQueryTimeline:
    """3e/1s/1h for query_timeline."""

    def test_happy_with_project_id(self) -> None:
        """Happy: returns entities filtered by project_id."""
        m = _make_mixin()
        node = _entity_node(id="e1", name="Event")
        m.select_graph().query.return_value = _mock_result([[node]])

        result = m.query_timeline("2026-01-01", "2026-12-31", project_id="proj-1")
        assert result == [{"id": "e1", "name": "Event"}]
        # Verify project_id was passed in params
        call_args = m.select_graph().query.call_args
        assert "project_id" in call_args[0][1]

    def test_happy_without_project_id(self) -> None:
        """Happy: returns entities without project filter."""
        m = _make_mixin()
        node = _entity_node(id="e2", name="Global")
        m.select_graph().query.return_value = _mock_result([[node]])

        result = m.query_timeline("2026-01-01", "2026-12-31")
        assert result == [{"id": "e2", "name": "Global"}]
        call_args = m.select_graph().query.call_args
        assert "project_id" not in call_args[0][1]

    def test_sad_empty_results(self) -> None:
        """Sad: no entities in time window."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.query_timeline("2099-01-01", "2099-12-31")
        assert result == []

    def test_evil_empty_row_filtered(self) -> None:
        """Evil: rows with falsy values are filtered out."""
        m = _make_mixin()
        node = _entity_node(id="e1", name="Valid")
        m.select_graph().query.return_value = _mock_result([[node], []])

        result = m.query_timeline("2026-01-01", "2026-12-31")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════
#  get_temporal_neighbors
# ═══════════════════════════════════════════════════════════════


class TestGetTemporalNeighbors:
    """3e/1s/1h for get_temporal_neighbors."""

    def test_happy_both_direction(self) -> None:
        """Happy: 'both' returns temporal neighbors."""
        m = _make_mixin()
        n1 = _entity_node(id="n1", name="Before")
        n2 = _entity_node(id="n2", name="After")
        m.select_graph().query.return_value = _mock_result([[n1], [n2]])

        result = m.get_temporal_neighbors("e1", direction="both")
        assert len(result) == 2

    def test_happy_before_direction(self) -> None:
        """Happy: 'before' filters to predecessors."""
        m = _make_mixin()
        n1 = _entity_node(id="n1", name="Predecessor")
        m.select_graph().query.return_value = _mock_result([[n1]])

        result = m.get_temporal_neighbors("e1", direction="before")
        assert len(result) == 1
        # Verify query uses correct direction pattern
        query_str = m.select_graph().query.call_args[0][0]
        assert "<-[r:" in query_str

    def test_happy_after_direction(self) -> None:
        """Happy: 'after' filters to successors."""
        m = _make_mixin()
        n1 = _entity_node(id="n1", name="Successor")
        m.select_graph().query.return_value = _mock_result([[n1]])

        result = m.get_temporal_neighbors("e1", direction="after")
        assert len(result) == 1
        query_str = m.select_graph().query.call_args[0][0]
        assert "->" in query_str

    def test_sad_no_neighbors(self) -> None:
        """Sad: entity has no temporal neighbors."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.get_temporal_neighbors("isolated")
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  create_temporal_edge
# ═══════════════════════════════════════════════════════════════


class TestCreateTemporalEdge:
    """3e/1s/1h for create_temporal_edge."""

    def test_happy_creates_edge(self) -> None:
        """Happy: creates temporal edge and returns result."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([["PRECEDED_BY", "from-1", "to-1"]])

        result = m.create_temporal_edge("from-1", "to-1")
        assert result["rel_type"] == "PRECEDED_BY"
        assert result["from_id"] == "from-1"
        assert result["to_id"] == "to-1"

    def test_happy_with_custom_properties(self) -> None:
        """Happy: custom properties are passed through."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([["EVOLVED_FROM", "a", "b"]])

        result = m.create_temporal_edge(
            "a", "b", edge_type="EVOLVED_FROM", properties={"weight": 0.5}
        )
        assert result["rel_type"] == "EVOLVED_FROM"
        # Verify props include custom + created_at
        call_args = m.select_graph().query.call_args
        props = call_args[0][1]["props"]
        assert "weight" in props
        assert "created_at" in props

    def test_sad_entity_not_found(self) -> None:
        """Sad: one or both entities not found returns error dict."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.create_temporal_edge("missing-1", "missing-2")
        assert "error" in result

    def test_evil_properties_none_gets_created_at(self) -> None:
        """Evil: None properties still gets created_at added."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([["PRECEDED_BY", "a", "b"]])

        m.create_temporal_edge("a", "b", properties=None)
        call_args = m.select_graph().query.call_args
        props = call_args[0][1]["props"]
        assert "created_at" in props


# ═══════════════════════════════════════════════════════════════
#  get_bottles
# ═══════════════════════════════════════════════════════════════


class TestGetBottles:
    """3e/1s/1h for get_bottles."""

    def test_happy_basic_query(self) -> None:
        """Happy: returns bottles with default filters."""
        m = _make_mixin()
        bottle = _entity_node(id="b1", name="Bottle-2026-01-01")
        m.select_graph().query.return_value = _mock_result([[bottle]])

        result = m.get_bottles()
        assert len(result) == 1

    def test_happy_all_filters(self) -> None:
        """Happy: all optional filters applied."""
        m = _make_mixin()
        bottle = _entity_node(id="b1", name="Bottle")
        m.select_graph().query.return_value = _mock_result([[bottle]])

        result = m.get_bottles(
            search_text="important",
            before_date="2026-12-31",
            after_date="2026-01-01",
            project_id="proj-1",
        )
        assert len(result) == 1
        # Verify all filter params are in the query params
        call_args = m.select_graph().query.call_args
        params = call_args[0][1]
        assert "text" in params
        assert "before" in params
        assert "after" in params
        assert "pid" in params

    def test_sad_no_bottles(self) -> None:
        """Sad: no bottles found."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.get_bottles()
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  get_graph_health
# ═══════════════════════════════════════════════════════════════


class TestGetGraphHealth:
    """3e/1s/1h for get_graph_health."""

    def test_happy_populated_graph(self) -> None:
        """Happy: returns health metrics for a graph with data."""
        m = _make_mixin()
        graph = m.select_graph()
        graph.query.side_effect = [
            _mock_result([[100]]),  # total nodes
            _mock_result([[80]]),  # entity count
            _mock_result([[20]]),  # observation count
            _mock_result([[150]]),  # total edges
            _mock_result([[5]]),  # orphan count
        ]

        result = m.get_graph_health()
        assert result["total_nodes"] == 100
        assert result["entity_count"] == 80
        assert result["observation_count"] == 20
        assert result["total_edges"] == 150
        assert result["orphan_count"] == 5
        assert result["avg_degree"] == 1.5  # 150/100
        assert "density" in result

    def test_sad_empty_graph(self) -> None:
        """Sad: empty graph returns zeros without division errors."""
        m = _make_mixin()
        graph = m.select_graph()
        graph.query.side_effect = [
            _mock_result([]),  # total nodes
            _mock_result([]),  # entity count
            _mock_result([]),  # observation count
            _mock_result([]),  # total edges
            _mock_result([]),  # orphan count
        ]

        result = m.get_graph_health()
        assert result["total_nodes"] == 0
        assert result["total_edges"] == 0
        assert result["avg_degree"] == 0.0

    def test_evil_single_node(self) -> None:
        """Evil: single node graph — density denominator is 1 (not 0)."""
        m = _make_mixin()
        graph = m.select_graph()
        graph.query.side_effect = [
            _mock_result([[1]]),  # total nodes
            _mock_result([[1]]),  # entity count
            _mock_result([[0]]),  # observation count
            _mock_result([[0]]),  # total edges
            _mock_result([[1]]),  # orphan count
        ]

        result = m.get_graph_health()
        assert result["density"] == 0.0  # 0 edges / 1 max


# ═══════════════════════════════════════════════════════════════
#  list_orphans
# ═══════════════════════════════════════════════════════════════


class TestListOrphans:
    """3e/1s/1h for list_orphans."""

    def test_happy_returns_orphans(self) -> None:
        """Happy: returns orphan nodes with all fields."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result(
            [["id-1", "Orphan Node", "Entity", "proj-1", "focus-1", ["Entity"], "2026-01-01"]]
        )

        result = m.list_orphans()
        assert len(result) == 1
        assert result[0]["id"] == "id-1"
        assert result[0]["name"] == "Orphan Node"
        assert result[0]["node_type"] == "Entity"
        assert result[0]["labels"] == ["Entity"]

    def test_sad_no_orphans(self) -> None:
        """Sad: no orphans in graph."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.list_orphans()
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  get_all_edges + get_all_node_ids
# ═══════════════════════════════════════════════════════════════


class TestGetAllEdges:
    """Tests for get_all_edges."""

    def test_happy_returns_edges(self) -> None:
        """Happy: returns edge list with source, target, type."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result(
            [["a", "b", "RELATED_TO"], ["b", "c", "ENABLES"]]
        )

        result = m.get_all_edges()
        assert len(result) == 2
        assert result[0] == {"source": "a", "target": "b", "type": "RELATED_TO"}

    def test_sad_no_edges(self) -> None:
        """Sad: no edges in graph."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.get_all_edges()
        assert result == []


class TestGetAllNodeIds:
    """Tests for get_all_node_ids."""

    def test_happy_returns_ids(self) -> None:
        """Happy: returns list of entity IDs."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([["id-1"], ["id-2"], ["id-3"]])

        result = m.get_all_node_ids()
        assert result == ["id-1", "id-2", "id-3"]

    def test_sad_empty(self) -> None:
        """Sad: no entities in graph."""
        m = _make_mixin()
        m.select_graph().query.return_value = _mock_result([])

        result = m.get_all_node_ids()
        assert result == []
