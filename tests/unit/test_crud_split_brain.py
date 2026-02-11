"""Tests for W3: Qdrant-down split-brain strict consistency in CrudMixin."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.crud import CrudMixin
from claude_memory.schema import EntityCreateParams


def _make_crud_mixin() -> CrudMixin:
    """Build a CrudMixin with all dependencies mocked."""
    mixin = CrudMixin.__new__(CrudMixin)
    mixin.repo = MagicMock()
    mixin.embedder = MagicMock()
    mixin.vector_store = AsyncMock()
    mixin.ontology = MagicMock()
    mixin.lock_manager = MagicMock()
    mixin._background_tasks = set()

    # Default happy-path returns
    mixin.ontology.is_valid_type.return_value = True
    mixin.repo.create_node.return_value = {"id": "test-123", "name": "Test"}
    mixin.repo.get_most_recent_entity.return_value = None
    mixin.repo.get_total_node_count.return_value = 42
    mixin.embedder.encode.return_value = [0.1] * 1024

    # Make the async context manager work
    mixin.lock_manager.lock.return_value = AsyncMock()

    return mixin


def _make_params() -> EntityCreateParams:
    """Build a minimal EntityCreateParams."""
    return EntityCreateParams(
        name="test-entity",
        node_type="Concept",
        project_id="test-project",
        properties={},
    )


@pytest.mark.asyncio
async def test_create_entity_qdrant_down_strict_raises() -> None:
    """When strict consistency is on and Qdrant fails, create_entity raises."""
    mixin = _make_crud_mixin()
    mixin.vector_store.upsert.side_effect = ConnectionError("Qdrant down")
    params = _make_params()

    with patch("claude_memory.crud.STRICT_CONSISTENCY", True):
        with pytest.raises(ConnectionError, match="Qdrant down"):
            await mixin.create_entity(params)


@pytest.mark.asyncio
async def test_create_entity_qdrant_down_lenient_warns() -> None:
    """When strict consistency is off, create_entity returns with warnings."""
    mixin = _make_crud_mixin()
    mixin.vector_store.upsert.side_effect = ConnectionError("Qdrant down")
    params = _make_params()

    with patch("claude_memory.crud.STRICT_CONSISTENCY", False):
        receipt = await mixin.create_entity(params)

    assert receipt.warnings
    assert "vector_upsert_failed" in receipt.warnings[0]
    assert receipt.id == "test-123"


@pytest.mark.asyncio
async def test_create_entity_qdrant_up_no_warnings() -> None:
    """When Qdrant is healthy, create_entity returns with no warnings."""
    mixin = _make_crud_mixin()
    params = _make_params()

    receipt = await mixin.create_entity(params)

    assert receipt.warnings == []
    assert receipt.id == "test-123"
