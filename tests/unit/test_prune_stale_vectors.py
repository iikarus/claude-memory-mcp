"""Tests for prune_stale() vector cleanup — Phase 1 BLOCKS SHIP fix.

Verifies that prune_stale() deletes Qdrant vectors BEFORE deleting
FalkorDB nodes, preventing orphan vectors (ghost search results).
"""

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from claude_memory.analysis import AnalysisMixin


def _make_analysis_mixin() -> AnalysisMixin:
    """Build an AnalysisMixin with all dependencies mocked."""
    mixin = AnalysisMixin.__new__(AnalysisMixin)
    mixin.repo = MagicMock()
    mixin.embedder = MagicMock()
    mixin.vector_store = AsyncMock()
    mixin.ontology = MagicMock()
    return mixin


def _make_cypher_result(rows: list[list]) -> MagicMock:
    """Create a mock Cypher query result."""
    result = MagicMock()
    result.result_set = rows
    return result


# ─── prune_stale: vector cleanup ────────────────────────────────────


@pytest.mark.asyncio
async def test_prune_stale_deletes_qdrant_vectors() -> None:
    """When pruning 3 stale entities, their Qdrant vectors are deleted."""
    mixin = _make_analysis_mixin()

    # First query returns IDs of stale entities
    mixin.repo.execute_cypher.side_effect = [
        _make_cypher_result([["id-1"], ["id-2"], ["id-3"]]),  # SELECT ids
        _make_cypher_result([[3]]),  # DETACH DELETE count
    ]

    result = await mixin.prune_stale(days=30)

    # Qdrant delete called for each ID
    assert mixin.vector_store.delete.await_count == 3
    mixin.vector_store.delete.assert_has_awaits(
        [call("id-1"), call("id-2"), call("id-3")], any_order=True
    )
    assert result["deleted_count"] == 3
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_prune_stale_no_stale_entities() -> None:
    """When no entities match, vector_store.delete is never called."""
    mixin = _make_analysis_mixin()

    mixin.repo.execute_cypher.return_value = _make_cypher_result([])

    result = await mixin.prune_stale(days=30)

    mixin.vector_store.delete.assert_not_awaited()
    assert result["deleted_count"] == 0


@pytest.mark.asyncio
async def test_prune_stale_qdrant_failure_propagates() -> None:
    """When Qdrant delete fails, the exception propagates (no silent failure)."""
    mixin = _make_analysis_mixin()

    mixin.repo.execute_cypher.return_value = _make_cypher_result([["id-1"]])
    mixin.vector_store.delete.side_effect = ConnectionError("Qdrant unreachable")

    with pytest.raises(ConnectionError, match="Qdrant unreachable"):
        await mixin.prune_stale(days=30)


@pytest.mark.asyncio
async def test_prune_stale_vectors_deleted_before_graph() -> None:
    """Qdrant vectors are deleted BEFORE graph nodes (order matters for recovery)."""
    mixin = _make_analysis_mixin()
    call_order: list[str] = []

    async def track_delete(id: str) -> None:
        call_order.append(f"qdrant_delete:{id}")

    def track_cypher(query: str, params: dict | None = None) -> MagicMock:
        if "DETACH DELETE" in query:
            call_order.append("graph_delete")
            return _make_cypher_result([[1]])
        # SELECT query
        call_order.append("graph_select")
        return _make_cypher_result([["id-1"]])

    mixin.vector_store.delete.side_effect = track_delete
    mixin.repo.execute_cypher.side_effect = track_cypher

    await mixin.prune_stale(days=30)

    assert call_order == ["graph_select", "qdrant_delete:id-1", "graph_delete"]
