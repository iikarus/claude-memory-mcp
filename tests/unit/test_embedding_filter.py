"""Tests for embedding field stripping — verify embeddings don't leak to API responses.

Phase 0 fix: patched MemoryRepository/LockManager/QdrantVectorStore/ActivationEngine
to prevent live connection attempts. Unskipped previously skipped tests.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.schema import EntityCreateParams


@pytest.fixture
def mock_service() -> Any:
    """Create a MemoryService with fully mocked infrastructure."""
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1] * 1024

    mock_repo = MagicMock()
    mock_repo.create_node.return_value = {
        "id": "123",
        "name": "Test",
        "node_type": "Entity",
        "project_id": "test",
        "embedding": [0.1] * 1024,  # simulate leak
    }
    mock_repo.get_total_node_count.return_value = 1
    mock_repo.get_most_recent_entity.return_value = None

    mock_vector = MagicMock()
    mock_vector.upsert = AsyncMock()
    mock_vector.search = AsyncMock(return_value=[])
    mock_vector.delete = AsyncMock()

    # Async context manager mock for lock
    lock_ctx = AsyncMock()
    lock_ctx.__aenter__ = AsyncMock(return_value=lock_ctx)
    lock_ctx.__aexit__ = AsyncMock(return_value=False)

    lock_manager_mock = MagicMock()
    lock_manager_mock.lock.return_value = lock_ctx

    with (
        patch("claude_memory.tools.MemoryRepository", return_value=mock_repo),
        patch("claude_memory.tools.LockManager", return_value=lock_manager_mock),
        patch("claude_memory.tools.QdrantVectorStore", return_value=mock_vector),
        patch("claude_memory.tools.ActivationEngine"),
    ):
        from claude_memory.tools import MemoryService

        service = MemoryService(embedding_service=mock_embedder)
        yield service


# ── Evil Tests ──────────────────────────────────────────────────────


async def test_get_hologram_evil_huge_embedding_stripped(mock_service: Any) -> None:
    """Evil: embeddings in subgraph nodes must be stripped to prevent context flood."""
    mock_service.repo.get_subgraph.return_value = {
        "nodes": [{"id": "1", "name": "Node", "embedding": [0.001] * 1536}],
        "edges": [],
    }

    # Mock search to return an anchor
    anchor_mock = MagicMock()
    anchor_mock.id = "1"
    anchor_mock.model_dump.return_value = {"id": "1", "name": "Node"}
    mock_service.search = AsyncMock(return_value=[anchor_mock])
    mock_service.context_manager.optimize = MagicMock(return_value=[{"id": "1", "name": "Node"}])

    result = await mock_service.get_hologram("query", depth=1)
    for node in result["nodes"]:
        assert "embedding" not in node, "Embedding leaked in hologram!"


async def test_get_neighbors_evil_embedding_in_properties(mock_service: Any) -> None:
    """Evil: node properties containing embedding must be stripped."""
    mock_node = MagicMock()
    mock_node.properties = {
        "id": "1",
        "name": "Neighbor",
        "embedding": [0.1] * 1024,
    }
    mock_row = [mock_node]
    mock_res = MagicMock()
    mock_res.result_set = [mock_row]
    mock_service.repo.execute_cypher.return_value = mock_res

    neighbors = await mock_service.get_neighbors("root_id")
    assert len(neighbors) == 1
    assert "embedding" not in neighbors[0], "get_neighbors leaked embedding!"


async def test_create_entity_evil_node_props_have_embedding(mock_service: Any) -> None:
    """Evil: repo returns node with embedding, receipt should NOT contain it."""
    params = EntityCreateParams(name="Test", node_type="Entity", project_id="test")
    receipt = await mock_service.create_entity(params)
    # EntityCommitReceipt is a Pydantic model that doesn't have 'embedding' field,
    # so even if the source data has it, the receipt won't.
    assert not hasattr(receipt, "embedding") or receipt.model_fields.get("embedding") is None
    # Verify it's a proper receipt
    assert receipt.id == "123"
    assert receipt.status == "committed"


# ── Sad Test ────────────────────────────────────────────────────────


async def test_get_hologram_sad_no_anchors(mock_service: Any) -> None:
    """Sad: search returns no anchors — should return empty hologram."""
    mock_service.search = AsyncMock(return_value=[])

    result = await mock_service.get_hologram("nonexistent query")
    assert result == {"nodes": [], "edges": []}


# ── Happy Test ──────────────────────────────────────────────────────


async def test_get_hologram_happy_clean_output(mock_service: Any) -> None:
    """Happy: hologram returns proper structure with stripped nodes."""
    anchor_mock = MagicMock()
    anchor_mock.id = "1"
    anchor_mock.model_dump.return_value = {"id": "1", "name": "Clean"}
    mock_service.search = AsyncMock(return_value=[anchor_mock])
    mock_service.repo.get_subgraph.return_value = {
        "nodes": [{"id": "1", "name": "Clean"}],
        "edges": [],
    }
    mock_service.context_manager.optimize = MagicMock(return_value=[{"id": "1", "name": "Clean"}])

    result = await mock_service.get_hologram("test query", depth=1)
    assert "nodes" in result
    assert "edges" in result
    assert "stats" in result
    assert result["stats"]["total_nodes"] == 1
