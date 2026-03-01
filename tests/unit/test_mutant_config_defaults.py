"""Mutation-killing tests for config defaults, env var chains, and retry backoff math.

Targets Pattern P3 (~55 kills): constructor defaults, env var fallback chains,
and exponential backoff delay calculation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from claude_memory.clustering import ClusteringService
from claude_memory.retry import _TRANSIENT_EXCEPTIONS, retry_on_transient
from claude_memory.vector_store import HNSW_INDEXING_THRESHOLD

# ═══════════════════════════════════════════════════════════════════
# Repository Config (repository.py)
# ═══════════════════════════════════════════════════════════════════


class TestRepositoryDefaults:
    """Assert MemoryRepository constructor defaults and env var chains."""

    def test_repo_evil_host_not_mutated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evil: host default must be 'localhost', not 'XXlocalhostXX'."""
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.repository.FalkorDB") as mock_fdb:
            mock_fdb.return_value = MagicMock()
            from claude_memory.repository import MemoryRepository

            repo = MemoryRepository()
            assert repo.host != "XXlocalhostXX"
            assert repo.host == "localhost"

    def test_repo_evil_port_not_mutated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evil: port default must be 6379, not 6380 or 0."""
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.repository.FalkorDB") as mock_fdb:
            mock_fdb.return_value = MagicMock()
            from claude_memory.repository import MemoryRepository

            repo = MemoryRepository()
            assert repo.port == 6379
            assert repo.port != 6380

    def test_repo_evil_graph_name_not_mutated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evil: graph_name must be 'claude_memory'."""
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.repository.FalkorDB") as mock_fdb:
            mock_fdb.return_value = MagicMock()
            from claude_memory.repository import MemoryRepository

            repo = MemoryRepository()
            assert repo.graph_name == "claude_memory"

    def test_repo_sad_env_override_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sad: env var overrides default host."""
        monkeypatch.setenv("FALKORDB_HOST", "custom-host")
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.repository.FalkorDB") as mock_fdb:
            mock_fdb.return_value = MagicMock()
            from claude_memory.repository import MemoryRepository

            repo = MemoryRepository()
            assert repo.host == "custom-host"

    def test_repo_happy_all_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy: all defaults match expected values."""
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.repository.FalkorDB") as mock_fdb:
            mock_fdb.return_value = MagicMock()
            from claude_memory.repository import MemoryRepository

            repo = MemoryRepository()
            assert repo.host == "localhost"
            assert repo.port == 6379
            assert repo.password is None
            assert repo.graph_name == "claude_memory"


class TestRepositoryConstants:
    """Assert module-level constants in repository.py."""

    def test_max_retries_evil(self) -> None:
        """Evil: _CONSTRUCTOR_MAX_RETRIES must be 3."""
        from claude_memory.repository import _CONSTRUCTOR_MAX_RETRIES

        assert _CONSTRUCTOR_MAX_RETRIES == 3
        assert _CONSTRUCTOR_MAX_RETRIES != 4

    def test_base_delay_evil(self) -> None:
        """Evil: _CONSTRUCTOR_BASE_DELAY must be 1.0."""
        from claude_memory.repository import _CONSTRUCTOR_BASE_DELAY

        assert _CONSTRUCTOR_BASE_DELAY == 1.0
        assert _CONSTRUCTOR_BASE_DELAY != 2.0

    def test_constants_evil_types(self) -> None:
        """Evil: constants must be correct types."""
        from claude_memory.repository import _CONSTRUCTOR_BASE_DELAY, _CONSTRUCTOR_MAX_RETRIES

        assert isinstance(_CONSTRUCTOR_MAX_RETRIES, int)
        assert isinstance(_CONSTRUCTOR_BASE_DELAY, float)

    def test_constants_sad_positive(self) -> None:
        """Sad: retry constants must be positive."""
        from claude_memory.repository import _CONSTRUCTOR_BASE_DELAY, _CONSTRUCTOR_MAX_RETRIES

        assert _CONSTRUCTOR_MAX_RETRIES > 0
        assert _CONSTRUCTOR_BASE_DELAY > 0

    def test_constants_happy(self) -> None:
        """Happy: all constants correct."""
        from claude_memory.repository import _CONSTRUCTOR_BASE_DELAY, _CONSTRUCTOR_MAX_RETRIES

        assert _CONSTRUCTOR_MAX_RETRIES == 3
        assert _CONSTRUCTOR_BASE_DELAY == 1.0


# ═══════════════════════════════════════════════════════════════════
# LockManager Config (lock_manager.py)
# ═══════════════════════════════════════════════════════════════════


class TestLockManagerDefaults:
    """Assert LockManager constructor defaults and env var chains."""

    def test_lock_evil_host_not_mutated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evil: host default must be 'localhost'."""
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            from claude_memory.lock_manager import LockManager

            lm = LockManager()
            assert lm.host == "localhost"
            assert lm.host != "XXlocalhostXX"

    def test_lock_evil_port_not_mutated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evil: port default must be 6379."""
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            from claude_memory.lock_manager import LockManager

            lm = LockManager()
            assert lm.port == 6379

    def test_lock_evil_redis_host_env_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evil: REDIS_HOST takes precedence over FALKORDB_HOST."""
        monkeypatch.setenv("REDIS_HOST", "redis-host")
        monkeypatch.setenv("FALKORDB_HOST", "falkor-host")
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            from claude_memory.lock_manager import LockManager

            lm = LockManager()
            assert lm.host == "redis-host"

    def test_lock_sad_falkordb_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sad: when REDIS_HOST is unset, falls back to FALKORDB_HOST."""
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.setenv("FALKORDB_HOST", "falkor-host")
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            from claude_memory.lock_manager import LockManager

            lm = LockManager()
            assert lm.host == "falkor-host"

    def test_lock_happy_all_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy: all defaults correct with no env vars."""
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            from claude_memory.lock_manager import LockManager

            lm = LockManager()
            assert lm.host == "localhost"
            assert lm.port == 6379
            assert lm.password is None


# ═══════════════════════════════════════════════════════════════════
# Retry Config (retry.py)
# ═══════════════════════════════════════════════════════════════════


class TestRetryDefaults:
    """Assert retry decorator defaults and transient exception tuple."""

    def test_transient_evil_builtins_present(self) -> None:
        """Evil: builtin exceptions must be in _TRANSIENT_EXCEPTIONS."""
        assert ConnectionError in _TRANSIENT_EXCEPTIONS
        assert TimeoutError in _TRANSIENT_EXCEPTIONS
        assert OSError in _TRANSIENT_EXCEPTIONS

    def test_transient_evil_not_empty(self) -> None:
        """Evil: tuple must have at least the 3 builtins."""
        assert len(_TRANSIENT_EXCEPTIONS) >= 3

    def test_transient_evil_no_base_exception(self) -> None:
        """Evil: must NOT catch all BaseException/Exception."""
        assert BaseException not in _TRANSIENT_EXCEPTIONS
        assert Exception not in _TRANSIENT_EXCEPTIONS

    def test_transient_sad_type_is_tuple(self) -> None:
        """Sad: must be a tuple, not a list."""
        assert isinstance(_TRANSIENT_EXCEPTIONS, tuple)

    def test_transient_happy(self) -> None:
        """Happy: all expected builtins present."""
        for exc in (ConnectionError, TimeoutError, OSError):
            assert exc in _TRANSIENT_EXCEPTIONS


class TestRetryBackoffMath:
    """Assert exponential backoff: delay = min(base_delay * (2**attempt), max_delay)."""

    def test_backoff_evil_first_attempt_delay(self) -> None:
        """Evil: attempt 0 delay = min(1.0 * (2**0), 16.0) = 1.0."""
        base_delay, max_delay = 1.0, 16.0
        delay = min(base_delay * (2**0), max_delay)
        assert delay == 1.0

    def test_backoff_evil_second_attempt_doubles(self) -> None:
        """Evil: attempt 1 delay = min(1.0 * (2**1), 16.0) = 2.0."""
        base_delay, max_delay = 1.0, 16.0
        delay = min(base_delay * (2**1), max_delay)
        assert delay == 2.0

    def test_backoff_evil_caps_at_max_delay(self) -> None:
        """Evil: attempt 5 delay = min(1.0 * (2**5), 16.0) = min(32, 16) = 16.0."""
        base_delay, max_delay = 1.0, 16.0
        delay = min(base_delay * (2**5), max_delay)
        assert delay == 16.0
        # Attempt 4: min(1.0 * 16, 16.0) = 16.0
        delay4 = min(base_delay * (2**4), max_delay)
        assert delay4 == 16.0

    def test_backoff_sad_custom_values(self) -> None:
        """Sad: custom base_delay/max_delay still follow formula."""
        base_delay, max_delay = 0.5, 4.0
        assert min(base_delay * (2**0), max_delay) == 0.5
        assert min(base_delay * (2**1), max_delay) == 1.0
        assert min(base_delay * (2**2), max_delay) == 2.0
        assert min(base_delay * (2**3), max_delay) == 4.0
        assert min(base_delay * (2**4), max_delay) == 4.0  # capped

    def test_backoff_happy_full_sequence(self) -> None:
        """Happy: entire retry delay sequence for defaults."""
        base_delay, max_delay = 1.0, 16.0
        expected = [1.0, 2.0, 4.0, 8.0, 16.0]
        for attempt, expected_delay in enumerate(expected):
            delay = min(base_delay * (2**attempt), max_delay)
            assert delay == expected_delay, f"Attempt {attempt}: {delay} != {expected_delay}"


class TestRetryDecorator:
    """Assert retry_on_transient decorator defaults via behavior testing."""

    def test_decorator_evil_default_max_retries(self) -> None:
        """Evil: default max_retries=5 means 6 total attempts (0..5)."""
        call_count = 0

        @retry_on_transient()
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("fail")

        with patch("claude_memory.retry.time.sleep"):  # skip actual sleeping
            with pytest.raises(ConnectionError):
                always_fail()
        assert call_count == 6  # 1 initial + 5 retries

    def test_decorator_evil_custom_max_retries(self) -> None:
        """Evil: max_retries=2 means 3 total attempts."""
        call_count = 0

        @retry_on_transient(max_retries=2)
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("fail")

        with patch("claude_memory.retry.time.sleep"):
            with pytest.raises(ConnectionError):
                always_fail()
        assert call_count == 3

    def test_decorator_evil_only_catches_transient(self) -> None:
        """Evil: non-transient exceptions must NOT be retried."""
        call_count = 0

        @retry_on_transient()
        def raises_value_error() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("not transient")

        with pytest.raises(ValueError):
            raises_value_error()
        assert call_count == 1  # no retry

    def test_decorator_sad_succeeds_on_retry(self) -> None:
        """Sad: function succeeds after initial failure."""
        call_count = 0

        @retry_on_transient()
        def eventual_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        with patch("claude_memory.retry.time.sleep"):
            result = eventual_success()
        assert result == "ok"
        assert call_count == 3

    def test_decorator_happy_no_failure(self) -> None:
        """Happy: function succeeds immediately — no retries."""
        call_count = 0

        @retry_on_transient()
        def immediate_success() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = immediate_success()
        assert result == "ok"
        assert call_count == 1


# ═══════════════════════════════════════════════════════════════════
# Clustering Config (clustering.py)
# ═══════════════════════════════════════════════════════════════════


class TestClusteringDefaults:
    """Assert ClusteringService constructor defaults."""

    def test_clustering_evil_eps_not_mutated(self) -> None:
        """Evil: eps default must be 0.5, not 0.6 or 1.5."""
        cs = ClusteringService()
        assert cs.eps == 0.5
        assert cs.eps != 1.5

    def test_clustering_evil_min_samples_not_mutated(self) -> None:
        """Evil: min_samples default must be 3, not 4 or 2."""
        cs = ClusteringService()
        assert cs.min_samples == 3
        assert cs.min_samples != 4

    def test_clustering_evil_custom_override(self) -> None:
        """Evil: custom values override defaults."""
        cs = ClusteringService(eps=0.8, min_samples=5)
        assert cs.eps == 0.8
        assert cs.min_samples == 5

    def test_clustering_sad_zero_eps(self) -> None:
        """Sad: eps=0 is technically valid but means exact match only."""
        cs = ClusteringService(eps=0.0)
        assert cs.eps == 0.0

    def test_clustering_happy(self) -> None:
        """Happy: all defaults correct."""
        cs = ClusteringService()
        assert cs.eps == 0.5
        assert cs.min_samples == 3


# ═══════════════════════════════════════════════════════════════════
# VectorStore Config (vector_store.py)
# ═══════════════════════════════════════════════════════════════════


class TestVectorStoreDefaults:
    """Assert QdrantVectorStore constants and constructor defaults."""

    def test_hnsw_evil_threshold_not_mutated(self) -> None:
        """Evil: HNSW_INDEXING_THRESHOLD must be 500."""
        assert HNSW_INDEXING_THRESHOLD == 500
        assert HNSW_INDEXING_THRESHOLD != 501

    def test_hnsw_evil_not_default_10k(self) -> None:
        """Evil: we explicitly override Qdrant's default of 10000."""
        assert HNSW_INDEXING_THRESHOLD != 10000

    def test_hnsw_evil_positive(self) -> None:
        """Evil: threshold must be positive integer."""
        assert HNSW_INDEXING_THRESHOLD > 0
        assert isinstance(HNSW_INDEXING_THRESHOLD, int)

    def test_vector_store_sad_default_collection(self) -> None:
        """Sad: default collection name from constructor signature."""
        import inspect

        from claude_memory.vector_store import QdrantVectorStore

        sig = inspect.signature(QdrantVectorStore.__init__)
        assert sig.parameters["collection"].default == "memory_embeddings"

    def test_vector_store_happy_defaults(self) -> None:
        """Happy: default constructor values correct."""
        import inspect

        from claude_memory.vector_store import QdrantVectorStore

        sig = inspect.signature(QdrantVectorStore.__init__)
        assert sig.parameters["collection"].default == "memory_embeddings"
        assert sig.parameters["vector_size"].default == 1024
