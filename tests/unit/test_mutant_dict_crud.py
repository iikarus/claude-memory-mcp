"""Mutation-killing tests for dict values — entity creation (crud.py).

Split from test_mutant_dict_values.py per 300-line module cap.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.schema import EntityCreateParams


def _make_mock_service() -> tuple:
    """Build mocked service infrastructure."""
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1] * 1024

    mock_repo = MagicMock()
    mock_repo.create_node.return_value = {
        "id": "test-id-123",
        "name": "Test",
        "node_type": "Entity",
        "project_id": "p1",
    }
    mock_repo.get_total_node_count.return_value = 42
    mock_repo.get_most_recent_entity.return_value = None

    mock_vector = MagicMock()
    mock_vector.upsert = AsyncMock()
    mock_vector.search = AsyncMock(return_value=[])

    lock_ctx = AsyncMock()
    lock_ctx.__aenter__ = AsyncMock(return_value=lock_ctx)
    lock_ctx.__aexit__ = AsyncMock(return_value=False)
    lock_mock = MagicMock()
    lock_mock.lock.return_value = lock_ctx

    return mock_embedder, mock_repo, mock_vector, lock_mock


def _build(e, r, v, lm):
    with (
        patch("claude_memory.tools.MemoryRepository", return_value=r),
        patch("claude_memory.tools.LockManager", return_value=lm),
        patch("claude_memory.tools.QdrantVectorStore", return_value=v),
        patch("claude_memory.tools.ActivationEngine"),
    ):
        from claude_memory.tools import MemoryService

        return MemoryService(embedding_service=e)


class TestCreateEntityProps:
    """Assert props dict passed to repo.create_node."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.lm = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.lm)

    async def test_evil_name(self) -> None:
        p = EntityCreateParams(name="Alpha", node_type="Entity", project_id="p1")
        await self.svc.create_entity(p)
        props = self.r.create_node.call_args[0][1]
        assert props["name"] == "Alpha"

    async def test_evil_node_type(self) -> None:
        p = EntityCreateParams(name="X", node_type="Concept", project_id="p1")
        await self.svc.create_entity(p)
        props = self.r.create_node.call_args[0][1]
        assert props["node_type"] == "Concept"

    async def test_evil_certainty(self) -> None:
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p1")
        await self.svc.create_entity(p)
        props = self.r.create_node.call_args[0][1]
        assert props["certainty"] == "confirmed"

    async def test_sad_initial_scores(self) -> None:
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p1")
        await self.svc.create_entity(p)
        props = self.r.create_node.call_args[0][1]
        assert props["salience_score"] == 1.0
        assert props["retrieval_count"] == 0

    async def test_happy_all_keys(self) -> None:
        await self.svc.create_entity(
            EntityCreateParams(
                name="T",
                node_type="Concept",
                project_id="my_p",
                certainty="speculative",
                evidence=["ev1"],
            )
        )
        t, props = self.r.create_node.call_args[0]
        assert t == "Concept"
        assert props["name"] == "T"
        assert props["project_id"] == "my_p"
        assert props["certainty"] == "speculative"
        assert "id" in props
        assert "created_at" in props


class TestCreateEntityReceipt:
    """Assert receipt returned by create_entity."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.lm = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.lm)

    async def test_evil_status(self) -> None:
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p1")
        receipt = await self.svc.create_entity(p)
        assert receipt.status == "committed"

    async def test_evil_id(self) -> None:
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p1")
        receipt = await self.svc.create_entity(p)
        assert receipt.id == "test-id-123"

    async def test_evil_name(self) -> None:
        p = EntityCreateParams(
            name="MyName",
            node_type="Entity",
            project_id="p1",
        )
        receipt = await self.svc.create_entity(p)
        assert receipt.name == "MyName"

    async def test_sad_total_count(self) -> None:
        self.r.get_total_node_count.return_value = 99
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p1")
        receipt = await self.svc.create_entity(p)
        assert receipt.total_memory_count == 99

    async def test_happy(self) -> None:
        p = EntityCreateParams(name="T", node_type="Entity", project_id="p1")
        receipt = await self.svc.create_entity(p)
        assert receipt.id == "test-id-123"
        assert receipt.status == "committed"
        assert receipt.total_memory_count == 42
        assert receipt.warnings == []
