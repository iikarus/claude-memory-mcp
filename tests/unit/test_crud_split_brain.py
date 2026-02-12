"""Tests for P-2: strict consistency — Qdrant failures always raise.

After removing the STRICT_CONSISTENCY toggle, vector operations must
always raise on failure. There is no lenient path.
"""

from unittest.mock import AsyncMock, MagicMock

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
async def test_create_entity_qdrant_down_always_raises() -> None:
    """When Qdrant is down, create_entity raises — no lenient path exists."""
    mixin = _make_crud_mixin()
    mixin.vector_store.upsert.side_effect = ConnectionError("Qdrant down")
    params = _make_params()

    with pytest.raises(ConnectionError, match="Qdrant down"):
        await mixin.create_entity(params)


@pytest.mark.asyncio
async def test_create_entity_qdrant_up_no_warnings() -> None:
    """When Qdrant is healthy, create_entity returns with empty warnings."""
    mixin = _make_crud_mixin()
    params = _make_params()

    receipt = await mixin.create_entity(params)

    assert receipt.warnings == []
    assert receipt.id == "test-123"


@pytest.mark.asyncio
async def test_strict_consistency_env_var_has_no_effect() -> None:
    """Even if env var were set to 'false', vector failure still raises.

    The toggle has been removed — this test proves it.
    """
    import os

    mixin = _make_crud_mixin()
    mixin.vector_store.upsert.side_effect = ConnectionError("Qdrant down")
    params = _make_params()

    old_val = os.environ.get("EXOCORTEX_STRICT_CONSISTENCY")
    try:
        os.environ["EXOCORTEX_STRICT_CONSISTENCY"] = "false"
        with pytest.raises(ConnectionError, match="Qdrant down"):
            await mixin.create_entity(params)
    finally:
        if old_val is None:
            os.environ.pop("EXOCORTEX_STRICT_CONSISTENCY", None)
        else:
            os.environ["EXOCORTEX_STRICT_CONSISTENCY"] = old_val
