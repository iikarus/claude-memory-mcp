"""Tests targeting specific uncovered lines to close coverage gaps.

Covers:
- graph_algorithms: empty inputs (L32, L123), no-edges louvain (L138)
- repository_queries: query_bottles optional filters (L169-176)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from claude_memory.graph_algorithms import compute_louvain, compute_pagerank

# ── graph_algorithms: empty inputs ──────────────────────────────────────


class TestPageRankEdgeCases:
    """Cover line 32: return [] for empty node list."""

    def test_empty_node_list_returns_empty(self) -> None:
        result = compute_pagerank(nodes={}, node_names=[], edges=[])
        assert result == []


class TestLouvainEdgeCases:
    """Cover lines 123 (empty list) and 138 (no edges)."""

    def test_empty_node_list_returns_empty(self) -> None:
        result = compute_louvain(nodes={}, node_names=[], edges=[])
        assert result == []

    def test_nodes_with_no_edges_each_own_community(self) -> None:
        nodes = {"A": MagicMock(), "B": MagicMock(), "C": MagicMock()}
        result = compute_louvain(nodes=nodes, node_names=["A", "B", "C"], edges=[])
        assert len(result) == 3
        for community in result:
            assert community["size"] == 1
            assert len(community["members"]) == 1

    def test_nodes_with_no_edges_caps_at_five(self) -> None:
        names = [f"N{i}" for i in range(10)]
        nodes = {n: MagicMock() for n in names}
        result = compute_louvain(nodes=nodes, node_names=names, edges=[])
        assert len(result) == 5
        for community in result:
            assert community["size"] == 1


# ── repository_queries: query_bottles optional filters ──────────────────


class TestQueryBottlesFilters:
    """Cover lines 169-176: before_date, after_date, project_id filters."""

    def _call_get_bottles(self, **kwargs: object) -> tuple[str, dict]:
        """Set up a mock RepositoryQueryMixin and call get_bottles.

        Returns the Cypher query string and params dict.
        """
        from claude_memory.repository_queries import RepositoryQueryMixin

        mock_node = MagicMock()
        mock_node.properties = {"id": "b1", "name": "Bottle", "node_type": "Bottle"}
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock_graph = MagicMock()
        mock_graph.query.return_value = mock_result

        # Build a minimal object implementing the mixin
        class _Repo(RepositoryQueryMixin):
            def select_graph(self):  # type: ignore[override]
                return mock_graph

        repo = object.__new__(_Repo)
        repo.get_bottles(**kwargs)  # type: ignore[arg-type]

        call_args = mock_graph.query.call_args
        return call_args[0][0], call_args[0][1]

    def test_before_date_filter(self) -> None:
        query, params = self._call_get_bottles(before_date="2026-06-01T00:00:00")
        assert "$before" in query
        assert params["before"] == "2026-06-01T00:00:00"

    def test_after_date_filter(self) -> None:
        query, params = self._call_get_bottles(after_date="2025-01-01T00:00:00")
        assert "$after" in query
        assert params["after"] == "2025-01-01T00:00:00"

    def test_project_id_filter(self) -> None:
        query, params = self._call_get_bottles(project_id="proj-42")
        assert "$pid" in query
        assert params["pid"] == "proj-42"

    def test_all_filters_combined(self) -> None:
        query, params = self._call_get_bottles(
            search_text="hello",
            before_date="2026-12-31",
            after_date="2025-01-01",
            project_id="proj-99",
        )
        assert "$text" in query
        assert "$before" in query
        assert "$after" in query
        assert "$pid" in query
        assert params["text"] == "hello"
        assert params["before"] == "2026-12-31"
        assert params["after"] == "2025-01-01"
        assert params["pid"] == "proj-99"
