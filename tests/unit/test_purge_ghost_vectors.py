"""Tests for purge_ghost_vectors.py — ghost detection and orphan cross-reference.

Covers:
  - _find_ghost_ids: empty-payload detection (3 evil / 1 happy)
  - _find_orphan_ids: graph cross-reference (3 evil / 1 sad / 1 happy)
  - main(): dry-run + execute modes
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import under controlled env
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
os.environ.setdefault("FALKORDB_HOST", "localhost")
os.environ.setdefault("FALKORDB_PORT", "6379")

from scripts.internal.purge_ghost_vectors import (
    _find_ghost_ids,
    _find_orphan_ids,
    _get_all_graph_ids,
    _scroll_all_ids,
    main,
)

# ─── Helpers ────────────────────────────────────────────────────────


def _make_point(pid: str, payload: dict | None = None) -> SimpleNamespace:
    """Create a mock Qdrant point."""
    return SimpleNamespace(id=pid, payload=payload)


def _mock_scroll_client(points_batches: list[list]) -> AsyncMock:
    """Create a mock Qdrant client with scroll returning given batches."""
    client = AsyncMock()
    # Each call returns (points, next_offset)
    # Last batch returns None as next_offset
    side_effects = []
    for i, batch in enumerate(points_batches):
        next_offset = f"offset_{i + 1}" if i < len(points_batches) - 1 else None
        side_effects.append((batch, next_offset))
    # Final call returns empty to stop
    side_effects.append(([], None))
    client.scroll.side_effect = side_effects
    return client


# ─── _find_ghost_ids Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_ghost_ids_detects_empty_payload() -> None:
    """EVIL: point with {} payload is detected as ghost."""
    points = [_make_point("id-1", {}), _make_point("id-2", {"name": "valid"})]
    client = _mock_scroll_client([points])
    result = await _find_ghost_ids(client)
    assert result == ["id-1"]


@pytest.mark.asyncio
async def test_find_ghost_ids_detects_none_payload() -> None:
    """EVIL: point with None payload is detected as ghost."""
    points = [_make_point("id-1", None)]
    client = _mock_scroll_client([points])
    result = await _find_ghost_ids(client)
    assert result == ["id-1"]


@pytest.mark.asyncio
async def test_find_ghost_ids_detects_no_name_no_type() -> None:
    """EVIL: point with payload but no name/node_type is ghost."""
    points = [_make_point("id-1", {"some_field": "value"})]
    client = _mock_scroll_client([points])
    result = await _find_ghost_ids(client)
    assert result == ["id-1"]


@pytest.mark.asyncio
async def test_find_ghost_ids_clean_collection() -> None:
    """HAPPY: all points have valid payloads — no ghosts."""
    points = [
        _make_point("id-1", {"name": "A", "node_type": "Entity"}),
        _make_point("id-2", {"name": "B", "node_type": "Observation"}),
    ]
    client = _mock_scroll_client([points])
    result = await _find_ghost_ids(client)
    assert result == []


# ─── _find_orphan_ids Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_orphan_ids_detects_missing_graph_node() -> None:
    """EVIL: Qdrant has ID not in graph → orphan."""
    points = [_make_point("id-1"), _make_point("id-2"), _make_point("id-3")]
    client = _mock_scroll_client([points])
    graph_ids = {"id-1", "id-3"}  # id-2 missing from graph

    orphans = await _find_orphan_ids(client, graph_ids=graph_ids)
    assert orphans == ["id-2"]


@pytest.mark.asyncio
async def test_find_orphan_ids_excludes_already_flagged() -> None:
    """EVIL: IDs already flagged as ghosts are excluded from orphan list."""
    points = [_make_point("id-1"), _make_point("id-2"), _make_point("id-3")]
    client = _mock_scroll_client([points])
    graph_ids = {"id-1"}  # id-2, id-3 not in graph
    exclude = {"id-2"}  # id-2 already flagged as ghost

    orphans = await _find_orphan_ids(client, graph_ids=graph_ids, exclude_ids=exclude)
    assert orphans == ["id-3"]


@pytest.mark.asyncio
async def test_find_orphan_ids_all_in_graph() -> None:
    """HAPPY: all Qdrant IDs exist in graph — no orphans."""
    points = [_make_point("id-1"), _make_point("id-2")]
    client = _mock_scroll_client([points])
    graph_ids = {"id-1", "id-2"}

    orphans = await _find_orphan_ids(client, graph_ids=graph_ids)
    assert orphans == []


@pytest.mark.asyncio
async def test_find_orphan_ids_empty_collection() -> None:
    """SAD: empty Qdrant collection — no orphans."""
    client = _mock_scroll_client([])
    graph_ids = {"id-1", "id-2"}

    orphans = await _find_orphan_ids(client, graph_ids=graph_ids)
    assert orphans == []


@pytest.mark.asyncio
async def test_find_orphan_ids_empty_graph() -> None:
    """EVIL: graph has no nodes — all Qdrant vectors are orphans."""
    points = [_make_point("id-1"), _make_point("id-2")]
    client = _mock_scroll_client([points])
    graph_ids: set[str] = set()

    orphans = await _find_orphan_ids(client, graph_ids=graph_ids)
    assert orphans == ["id-1", "id-2"]


# ─── _get_all_graph_ids Tests ───────────────────────────────────────


def test_get_all_graph_ids_returns_set() -> None:
    """HAPPY: returns set of string IDs from graph query."""
    mock_result = MagicMock()
    mock_result.result_set = [["uuid-1"], ["uuid-2"], ["uuid-3"]]

    mock_graph = MagicMock()
    mock_graph.query.return_value = mock_result

    mock_db = MagicMock()
    mock_db.select_graph.return_value = mock_graph

    with patch("falkordb.FalkorDB", return_value=mock_db):
        result = _get_all_graph_ids()

    assert result == {"uuid-1", "uuid-2", "uuid-3"}


# ─── _scroll_all_ids Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_scroll_all_ids_multiple_batches() -> None:
    """HAPPY: scrolls multiple batches and returns all IDs."""
    batch1 = [_make_point("id-1"), _make_point("id-2")]
    batch2 = [_make_point("id-3")]
    client = _mock_scroll_client([batch1, batch2])

    result = await _scroll_all_ids(client)
    assert result == ["id-1", "id-2", "id-3"]


# ─── main() Integration Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_main_dry_run_reports_both_categories() -> None:
    """HAPPY: dry-run reports ghosts and orphans separately."""
    ghost_point = _make_point("ghost-1", {})
    valid_point = _make_point("orphan-1", {"name": "A", "node_type": "Entity"})
    graph_point = _make_point("ok-1", {"name": "B", "node_type": "Entity"})

    mock_client = AsyncMock()
    # _find_ghost_ids scroll: returns all points with payload
    # _scroll_all_ids (orphan pass): returns all IDs without payload
    mock_client.scroll.side_effect = [
        # Pass 1 (_find_ghost_ids): one batch then empty
        ([ghost_point, valid_point, graph_point], None),
        ([], None),
        # Pass 2 (_scroll_all_ids via _find_orphan_ids): one batch then empty
        ([_make_point("ghost-1"), _make_point("orphan-1"), _make_point("ok-1")], None),
        ([], None),
    ]
    mock_client.close = AsyncMock()

    with (
        patch("qdrant_client.AsyncQdrantClient", return_value=mock_client),
        patch("scripts.internal.purge_ghost_vectors._get_all_graph_ids", return_value={"ok-1"}),
    ):
        await main([])  # dry-run

    # Should not delete anything in dry-run
    mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_main_execute_deletes_combined() -> None:
    """HAPPY: --execute deletes both ghosts and orphans."""
    ghost_point = _make_point("ghost-1", {})
    orphan_point = _make_point("orphan-1", {"name": "A", "node_type": "Entity"})

    mock_client = AsyncMock()
    mock_client.scroll.side_effect = [
        # Pass 1 (_find_ghost_ids)
        ([ghost_point, orphan_point], None),
        ([], None),
        # Pass 2 (_scroll_all_ids via _find_orphan_ids)
        ([_make_point("ghost-1"), _make_point("orphan-1")], None),
        ([], None),
    ]
    mock_client.close = AsyncMock()
    mock_client.delete = AsyncMock()

    with (
        patch("qdrant_client.AsyncQdrantClient", return_value=mock_client),
        patch("scripts.internal.purge_ghost_vectors._get_all_graph_ids", return_value=set()),
    ):
        await main(["--execute"])

    # Should delete with combined IDs (ghosts + orphans)
    mock_client.delete.assert_called_once()
