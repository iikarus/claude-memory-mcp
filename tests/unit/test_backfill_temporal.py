"""Tests for scripts/backfill_temporal.py migration functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# We import the module functions directly — no live DB needed.
from scripts.internal.backfill_temporal import (
    backfill_occurred_at,
    create_preceded_by_edges,
    get_project_ids,
    main,
)

# ─── Test Constants ─────────────────────────────────────────────────

PROJECT_A = "project-alpha"
PROJECT_B = "project-beta"


# ─── Helpers ────────────────────────────────────────────────────────


def _mock_query_result(rows: list[list]) -> MagicMock:
    """Build a mock FalkorDB query result."""
    result = MagicMock()
    result.result_set = rows
    return result


# ─── backfill_occurred_at Tests ─────────────────────────────────────


def test_backfill_occurred_at_all_set() -> None:
    """When all entities already have occurred_at, returns 0."""
    graph = MagicMock()
    graph.query.return_value = _mock_query_result([[0]])

    count = backfill_occurred_at(graph, dry_run=False)
    assert count == 0
    # Only count query should be called (no update needed)
    assert graph.query.call_count == 1


def test_backfill_occurred_at_dry_run() -> None:
    """Dry-run returns count but does NOT execute update query."""
    graph = MagicMock()
    graph.query.return_value = _mock_query_result([[42]])

    count = backfill_occurred_at(graph, dry_run=True)
    assert count == 42
    # Only count query — no mutation
    assert graph.query.call_count == 1


def test_backfill_occurred_at_execute() -> None:
    """Execute mode runs count query then update query."""
    graph = MagicMock()
    graph.query.side_effect = [
        _mock_query_result([[15]]),  # count query
        _mock_query_result([[15]]),  # update query
    ]

    count = backfill_occurred_at(graph, dry_run=False)
    assert count == 15
    assert graph.query.call_count == 2


# ─── get_project_ids Tests ──────────────────────────────────────────


def test_get_project_ids() -> None:
    """Returns distinct project IDs."""
    graph = MagicMock()
    graph.query.return_value = _mock_query_result([[PROJECT_A], [PROJECT_B]])

    result = get_project_ids(graph)
    assert result == [PROJECT_A, PROJECT_B]


def test_get_project_ids_empty() -> None:
    """Returns empty list when no projects found."""
    graph = MagicMock()
    graph.query.return_value = _mock_query_result([])

    result = get_project_ids(graph)
    assert result == []


# ─── create_preceded_by_edges Tests ─────────────────────────────────


def test_create_preceded_by_dry_run() -> None:
    """Dry-run counts missing edges but does not create them."""
    graph = MagicMock()
    # Query flow: project list → entity order → check pair(a,b) → check pair(b,c)
    graph.query.side_effect = [
        _mock_query_result([[PROJECT_A]]),  # project list
        _mock_query_result([["id-1"], ["id-2"], ["id-3"]]),  # entity IDs
        _mock_query_result([[0]]),  # pair (id-1, id-2) missing
        _mock_query_result([[1]]),  # pair (id-2, id-3) exists
    ]

    summary = create_preceded_by_edges(graph, dry_run=True)
    assert summary == {PROJECT_A: 1}
    # No CREATE query executed
    assert graph.query.call_count == 4


def test_create_preceded_by_execute() -> None:
    """Execute mode creates edges for missing pairs."""
    graph = MagicMock()
    # Query flow: project list → entity order → check pair → create pair
    graph.query.side_effect = [
        _mock_query_result([[PROJECT_A]]),  # project list
        _mock_query_result([["id-1"], ["id-2"]]),  # entity IDs
        _mock_query_result([[0]]),  # pair (id-1, id-2) missing
        _mock_query_result([]),  # CREATE result
    ]

    summary = create_preceded_by_edges(graph, dry_run=False)
    assert summary == {PROJECT_A: 1}
    assert graph.query.call_count == 4


def test_create_preceded_by_no_projects() -> None:
    """Returns empty dict when no projects found."""
    graph = MagicMock()
    graph.query.return_value = _mock_query_result([])

    summary = create_preceded_by_edges(graph, dry_run=True)
    assert summary == {}


def test_create_preceded_by_zero_edges() -> None:
    """Projects with all edges present are skipped."""
    graph = MagicMock()
    graph.query.side_effect = [
        _mock_query_result([[PROJECT_A]]),  # project list
        _mock_query_result([["id-1"], ["id-2"]]),  # entity IDs
        _mock_query_result([[1]]),  # pair exists → skip
    ]

    summary = create_preceded_by_edges(graph, dry_run=False)
    assert summary == {}


# ─── CLI main() Tests ───────────────────────────────────────────────


@patch("scripts.internal.backfill_temporal._get_graph")
def test_main_dry_run_default(mock_get_graph: MagicMock) -> None:
    """main() defaults to dry-run mode."""
    graph = MagicMock()
    mock_get_graph.return_value = graph
    # backfill count + edge project list
    graph.query.side_effect = [
        _mock_query_result([[0]]),  # backfill count
        _mock_query_result([]),  # project list
    ]

    main([])  # no --execute
    mock_get_graph.assert_called_once()


@patch("scripts.internal.backfill_temporal._get_graph")
def test_main_execute_flag(mock_get_graph: MagicMock) -> None:
    """main() with --execute runs mutations."""
    graph = MagicMock()
    mock_get_graph.return_value = graph
    graph.query.side_effect = [
        _mock_query_result([[0]]),  # backfill count (all set)
        _mock_query_result([]),  # project list
    ]

    main(["--execute"])
    mock_get_graph.assert_called_once()
