"""Tests for P-1: consolidate_memories error accumulation.

Verifies that when archiving one entity fails, the others are still
archived and the error list surfaces the failure.
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

    # Default happy-path returns
    mixin.repo.create_node.return_value = {"id": "new-123", "name": "Consolidated"}
    mixin.embedder.encode.return_value = [0.1] * 1024

    return mixin


@pytest.mark.asyncio
async def test_partial_failure_still_archives_others() -> None:
    """When archiving one of three entities fails, the other two are archived."""
    mixin = _make_analysis_mixin()

    # Make create_edge succeed for all, but update_node fails for "entity-2"
    def _update_node_side_effect(entity_id: str, props: dict) -> dict:
        if entity_id == "entity-2":
            raise ConnectionError("FalkorDB connection lost")
        return {"id": entity_id, **props}

    mixin.repo.create_edge.return_value = {"id": "edge-1"}
    mixin.repo.update_node.side_effect = _update_node_side_effect

    result = await mixin.consolidate_memories(
        entity_ids=["entity-1", "entity-2", "entity-3"],
        summary="test consolidation",
    )

    # Entity-2 failed, but entity-1 and entity-3 should still be archived
    assert mixin.repo.update_node.call_count == 3  # All three attempted
    assert "consolidation_errors" in result
    assert len(result["consolidation_errors"]) == 1
    assert "entity-2" in result["consolidation_errors"][0]


@pytest.mark.asyncio
async def test_all_succeed_no_errors() -> None:
    """When all entities archive successfully, no consolidation_errors key."""
    mixin = _make_analysis_mixin()
    mixin.repo.create_edge.return_value = {"id": "edge-1"}
    mixin.repo.update_node.return_value = {"id": "ok"}

    result = await mixin.consolidate_memories(
        entity_ids=["entity-1", "entity-2"],
        summary="clean merge",
    )

    assert "consolidation_errors" not in result
