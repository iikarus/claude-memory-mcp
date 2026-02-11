import time
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.lock_manager import LockManager
from claude_memory.tools import EntityCreateParams, EntityUpdateParams, MemoryService


@pytest.fixture
def mock_redis() -> Generator[MagicMock, None, None]:
    with patch("claude_memory.lock_manager.redis.Redis") as mock_redis_cls:
        mock_client = mock_redis_cls.return_value
        # Default behavior: Access granted
        mock_client.set.return_value = True
        yield mock_client


class TestLockManager:
    def test_acquire_success(self, mock_redis: MagicMock) -> None:
        manager = LockManager()
        assert manager.acquire("p1") is True
        mock_redis.set.assert_called()

    def test_acquire_failure(self, mock_redis: MagicMock) -> None:
        manager = LockManager()
        # Simulate lock held (set returns False)
        mock_redis.set.return_value = False

        # Should return False after timeout (using short timeout for test)
        start = time.time()
        assert manager.acquire("p1", timeout=0.1) is False
        duration = time.time() - start
        assert duration >= 0.1

    def test_release(self, mock_redis: MagicMock) -> None:
        manager = LockManager()
        manager.release("p1")
        mock_redis.delete.assert_called_with("lock:project:p1")

    def test_context_manager(self, mock_redis: MagicMock) -> None:
        manager = LockManager()
        with manager.lock("p1"):
            pass
        mock_redis.set.assert_called()
        mock_redis.delete.assert_called()


@pytest.fixture
def mock_service_with_lock(mock_redis: MagicMock) -> Generator[MemoryService, None, None]:
    with (
        patch("claude_memory.embedding.EmbeddingService"),
        patch("claude_memory.repository.FalkorDB"),
        patch("claude_memory.tools.QdrantVectorStore"),
    ):
        service = MemoryService(embedding_service=MagicMock())
        # Make vector_store methods compatible with await
        service.vector_store.upsert = AsyncMock()
        service.vector_store.delete = AsyncMock()

        # The service instantiates LockManager internally, which uses the patched redis
        yield service


@pytest.mark.asyncio
async def test_create_entity_locks_project(
    mock_service_with_lock: MemoryService, mock_redis: MagicMock
) -> None:
    params = EntityCreateParams(name="Test", node_type="Entity", project_id="p1")

    # Mock ontology validation
    mock_service_with_lock.ontology.is_valid_type = MagicMock(return_value=True)
    # Mock repo create
    mock_service_with_lock.repo.create_node = MagicMock(return_value={"id": "1", "name": "Test"})
    mock_service_with_lock.repo.get_total_node_count = MagicMock(return_value=1)

    await mock_service_with_lock.create_entity(params)

    # Verify lock was acquired for "p1"
    # The key should be "lock:project:p1"
    # We can check if `set` was called with this key
    calls = mock_redis.set.call_args_list
    assert any("lock:project:p1" in str(c) for c in calls)

    # Verify release
    mock_redis.delete.assert_called_with("lock:project:p1")


@pytest.mark.asyncio
async def test_update_entity_locks_project(
    mock_service_with_lock: MemoryService, mock_redis: MagicMock
) -> None:
    params = EntityUpdateParams(entity_id="e1", properties={"name": "New"})

    # Mock existing node fetch to return project_id
    mock_service_with_lock.repo.get_node = MagicMock(return_value={"id": "e1", "project_id": "p2"})
    mock_service_with_lock.repo.update_node = MagicMock(return_value={"id": "e1"})

    await mock_service_with_lock.update_entity(params)

    # Verify lock for "p2"
    mock_redis.set.assert_called()
    # Check specifically for p2. Since create might have run, check calls.
    # But fixture creates fresh service, but `mock_redis` fixture might be shared if not scoped?
    # Pytest fixtures are function-scoped by default.
    calls = mock_redis.set.call_args_list
    assert any("lock:project:p2" in str(c) for c in calls)
    mock_redis.delete.assert_called_with("lock:project:p2")


# ─── Env Var Precedence Tests ───────────────────────────────────────


def test_redis_host_takes_precedence(mock_redis: MagicMock) -> None:
    """REDIS_HOST should override FALKORDB_HOST."""
    env = {
        "REDIS_HOST": "redis-primary",
        "FALKORDB_HOST": "graph-host",
        "REDIS_PORT": "6380",
        "FALKORDB_PORT": "6379",
    }
    with patch.dict("os.environ", env, clear=False):
        mgr = LockManager()
    assert mgr.host == "redis-primary"
    assert mgr.port == 6380


def test_falkordb_host_fallback(mock_redis: MagicMock) -> None:
    """Without REDIS_HOST, should fall back to FALKORDB_HOST."""
    env = {"FALKORDB_HOST": "graph-host", "FALKORDB_PORT": "6379"}
    with patch.dict("os.environ", env, clear=False):
        # Clear REDIS_* to ensure fallback
        with patch.dict(
            "os.environ",
            {"REDIS_HOST": "", "REDIS_PORT": ""},
        ):
            mgr = LockManager()
    assert mgr.host == "graph-host"
    assert mgr.port == 6379
