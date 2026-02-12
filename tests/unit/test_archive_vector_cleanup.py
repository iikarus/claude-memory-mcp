"""Tests for archive_entity() vector cleanup — Phase 2 SHOULD FIX.

Verifies that archive_entity() deletes the Qdrant vector when archiving
an entity, and that Qdrant failures propagate to the caller.
"""

from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_archive_entity_deletes_qdrant_vector() -> None:
    """Archiving an entity deletes its Qdrant vector."""
    mixin = _make_analysis_mixin()
    mixin.repo.update_node.return_value = {"id": "ent-1", "status": "archived"}

    result = await mixin.archive_entity("ent-1")

    mixin.vector_store.delete.assert_awaited_once_with("ent-1")
    assert result["status"] == "archived"


@pytest.mark.asyncio
async def test_archive_entity_qdrant_failure_propagates() -> None:
    """When Qdrant delete fails during archive, exception propagates."""
    mixin = _make_analysis_mixin()
    mixin.vector_store.delete.side_effect = ConnectionError("Qdrant unreachable")

    with pytest.raises(ConnectionError, match="Qdrant unreachable"):
        await mixin.archive_entity("ent-1")


@pytest.mark.asyncio
async def test_archive_entity_vector_deleted_before_graph_update() -> None:
    """Vector deletion happens BEFORE graph status update."""
    mixin = _make_analysis_mixin()
    call_order: list[str] = []

    async def track_delete(id: str) -> None:
        call_order.append("qdrant_delete")

    def track_update(entity_id: str, props: dict) -> dict:
        call_order.append("graph_update")
        return {"id": entity_id, "status": "archived"}

    mixin.vector_store.delete.side_effect = track_delete
    mixin.repo.update_node.side_effect = track_update

    await mixin.archive_entity("ent-1")

    assert call_order == ["qdrant_delete", "graph_update"]
