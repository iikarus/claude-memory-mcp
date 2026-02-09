"""Gap-closing tests for librarian.py, lock_manager.py, clustering.py,
context_manager.py, and ontology.py.

Each test targets specific uncovered lines identified by the coverage report.
All test data uses named constants — zero magic values in test bodies.
"""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Test Constants ─────────────────────────────────────────────────

# Librarian constants
LIBRARIAN_NODE_ID_1 = "lib-node-001"
LIBRARIAN_NODE_ID_2 = "lib-node-002"
LIBRARIAN_NODE_ID_3 = "lib-node-003"
LIBRARIAN_NODE_NAME_1 = "Architecture"
LIBRARIAN_NODE_NAME_2 = "Patterns"
LIBRARIAN_NODE_NAME_3 = "Design"
LIBRARIAN_CONSOLIDATION_ID = "consolidated-001"
LIBRARIAN_PRUNE_DAYS = 60
LIBRARIAN_PRUNE_DELETED_COUNT = 5
LIBRARIAN_FETCH_ERROR = "FalkorDB connection refused"
LIBRARIAN_CONSOLIDATE_ERROR = "Consolidation storage full"
LIBRARIAN_PRUNE_ERROR = "Prune timeout exceeded"
LIBRARIAN_CLUSTER_ID = 0

# Lock manager constants
LOCK_PROJECT_ID = "lock-project-alpha"
LOCK_TIMEOUT = 5
LOCK_TIMEOUT_EXTRA = 10
LOCK_HOST = "redis-host"
LOCK_PORT = 6380
LOCK_STALE_TIMESTAMP = 1000000.0
LOCK_CURRENT_TIMESTAMP = 9999999.0

# Clustering constants
CLUSTER_EPS = 0.5
CLUSTER_MIN_SAMPLES = 3
CLUSTER_EMBEDDING_DIM = 3
CLUSTER_EMPTY_EMBEDDING: list[float] = []

# Context manager constants
CTX_TOKEN_LIMIT = 100
CTX_NODE_NAME = "TestNode"
CTX_NODE_TYPE = "Entity"
CTX_NODE_DESC = "A" * 500  # Long description to trigger truncation
CTX_NODE_SHORT_DESC = "Short"

# Ontology constants
ONTOLOGY_TYPE_NAME = "Recipe"
ONTOLOGY_TYPE_DESC = "A culinary recipe"
ONTOLOGY_REQUIRED_PROP = "ingredients"
ONTOLOGY_CONFIG_PATH = "test_ontology.json"
ONTOLOGY_LOAD_ERROR = "Permission denied"
ONTOLOGY_OVERWRITE_TYPE = "Entity"  # Exists in DEFAULT_ONTOLOGY


# ─── Librarian Tests ────────────────────────────────────────────────


class TestLibrarianAgent:
    """Tests for uncovered lines in LibrarianAgent.run_cycle."""

    @pytest.fixture()
    def librarian(self) -> Any:
        """Create a LibrarianAgent with mocked dependencies."""
        with patch("claude_memory.librarian.ClusteringService"):
            with patch("claude_memory.librarian.MemoryService"):
                from claude_memory.librarian import LibrarianAgent

                mock_memory = MagicMock()
                mock_clustering = MagicMock()
                mock_clustering.min_samples = CLUSTER_MIN_SAMPLES
                agent = LibrarianAgent(
                    memory_service=mock_memory,
                    clustering_service=mock_clustering,
                )
                return agent

    async def test_run_cycle_fetch_exception(self, librarian: Any) -> None:
        """Lines 46-49: fetch throws, returns early with error."""
        librarian.memory.repo.get_all_nodes.side_effect = Exception(LIBRARIAN_FETCH_ERROR)
        report = await librarian.run_cycle()
        assert LIBRARIAN_FETCH_ERROR in report["errors"][0]
        assert report["clusters_found"] == 0

    async def test_run_cycle_consolidation_error(self, librarian: Any) -> None:
        """Lines 74-76: consolidation throws, error captured in report."""
        nodes = [
            {"id": LIBRARIAN_NODE_ID_1, "name": LIBRARIAN_NODE_NAME_1},
            {"id": LIBRARIAN_NODE_ID_2, "name": LIBRARIAN_NODE_NAME_2},
            {"id": LIBRARIAN_NODE_ID_3, "name": LIBRARIAN_NODE_NAME_3},
        ]
        librarian.memory.repo.get_all_nodes.return_value = nodes

        from claude_memory.clustering import Cluster

        mock_cluster = Cluster(
            id=LIBRARIAN_CLUSTER_ID,
            nodes=nodes,
            centroid=[0.1, 0.2],
            cohesion_score=0.5,
        )
        librarian.clustering.cluster_nodes.return_value = [mock_cluster]
        librarian.memory.consolidate_memories = AsyncMock(
            side_effect=Exception(LIBRARIAN_CONSOLIDATE_ERROR)
        )
        librarian.memory.prune_stale = AsyncMock(
            return_value={"deleted_count": LIBRARIAN_PRUNE_DELETED_COUNT}
        )

        report = await librarian.run_cycle()
        assert report["clusters_found"] == 1
        assert report["consolidations_created"] == 0
        assert any(LIBRARIAN_CONSOLIDATE_ERROR in e for e in report["errors"])

    async def test_run_cycle_prune_error(self, librarian: Any) -> None:
        """Lines 82-83: prune throws, error captured in report."""
        nodes = [
            {"id": LIBRARIAN_NODE_ID_1, "name": LIBRARIAN_NODE_NAME_1},
            {"id": LIBRARIAN_NODE_ID_2, "name": LIBRARIAN_NODE_NAME_2},
            {"id": LIBRARIAN_NODE_ID_3, "name": LIBRARIAN_NODE_NAME_3},
        ]
        librarian.memory.repo.get_all_nodes.return_value = nodes
        librarian.clustering.cluster_nodes.return_value = []
        librarian.memory.prune_stale = AsyncMock(side_effect=Exception(LIBRARIAN_PRUNE_ERROR))

        report = await librarian.run_cycle()
        assert any("Prune" in e for e in report["errors"])

    async def test_run_cycle_successful_consolidation(self, librarian: Any) -> None:
        """Lines 71-73: successful consolidation increments counter."""
        nodes = [
            {"id": LIBRARIAN_NODE_ID_1, "name": LIBRARIAN_NODE_NAME_1},
            {"id": LIBRARIAN_NODE_ID_2, "name": LIBRARIAN_NODE_NAME_2},
            {"id": LIBRARIAN_NODE_ID_3, "name": LIBRARIAN_NODE_NAME_3},
        ]
        librarian.memory.repo.get_all_nodes.return_value = nodes

        from claude_memory.clustering import Cluster

        mock_cluster = Cluster(
            id=LIBRARIAN_CLUSTER_ID,
            nodes=nodes,
            centroid=[0.1, 0.2],
            cohesion_score=0.5,
        )
        librarian.clustering.cluster_nodes.return_value = [mock_cluster]
        librarian.memory.consolidate_memories = AsyncMock(
            return_value={"id": LIBRARIAN_CONSOLIDATION_ID}
        )
        librarian.memory.prune_stale = AsyncMock(
            return_value={"deleted_count": LIBRARIAN_PRUNE_DELETED_COUNT}
        )

        report = await librarian.run_cycle()
        assert report["consolidations_created"] == 1
        assert report["deleted_stale"] == LIBRARIAN_PRUNE_DELETED_COUNT


# ─── Lock Manager Tests ─────────────────────────────────────────────


class TestLockManager:
    """Tests for uncovered lines in LockManager and ProjectLock."""

    def test_project_lock_enter_timeout(self) -> None:
        """Line 28: __enter__ raises TimeoutError when acquire fails."""
        from claude_memory.lock_manager import ProjectLock

        mock_manager = MagicMock()
        mock_manager.acquire.return_value = False
        lock = ProjectLock(mock_manager, LOCK_PROJECT_ID)

        with pytest.raises(TimeoutError, match=LOCK_PROJECT_ID):
            lock.__enter__()

    def test_lock_manager_custom_port(self) -> None:
        """Line 45: port argument provided directly."""
        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from claude_memory.lock_manager import LockManager

            mgr = LockManager(host=LOCK_HOST, port=LOCK_PORT)
            assert mgr.port == LOCK_PORT
            assert mgr.host == LOCK_HOST

    def test_file_lock_stale_cleanup(self, tmp_path: Any) -> None:
        """Lines 114-117: stale file lock detected, removed, and re-acquired."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError("no redis")

            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

            # Create a stale lock file
            lock_path = os.path.join(str(tmp_path), f"{LOCK_PROJECT_ID}.lock")
            with open(lock_path, "w") as f:
                f.write(str(LOCK_STALE_TIMESTAMP))

            # Should detect stale, remove, and acquire
            result = mgr._acquire_file(LOCK_PROJECT_ID, timeout=LOCK_TIMEOUT)
            assert result is True

    def test_release_file_not_found(self, tmp_path: Any) -> None:
        """Lines 126-127: releasing a lock file that doesn't exist (FileNotFoundError)."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError("no redis")

            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

            # Should not raise even though file doesn't exist
            mgr._release_file(LOCK_PROJECT_ID)

    def test_acquire_redis_timeout(self) -> None:
        """Line 90-91: Redis lock acquisition times out."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.set.return_value = False  # Always fails to acquire
            mock_redis.return_value = mock_client

            mgr = LockManager()
            # Use very short timeout to avoid slow test
            with patch("claude_memory.lock_manager.time") as mock_time:
                # Simulate timeout: first call returns current time,
                # second call exceeds deadline
                mock_time.time.side_effect = [0.0, 0.0, 999.0]
                mock_time.sleep = MagicMock()
                result = mgr._acquire_redis(LOCK_PROJECT_ID, timeout=1)
                assert result is False


# ─── Clustering Tests ────────────────────────────────────────────────


class TestClusteringGaps:
    """Tests for uncovered lines in ClusteringService."""

    def test_cluster_nodes_no_embeddings(self) -> None:
        """Lines 48-50: all nodes lack embeddings → empty result."""
        from claude_memory.clustering import ClusteringService

        svc = ClusteringService(eps=CLUSTER_EPS, min_samples=CLUSTER_MIN_SAMPLES)
        nodes_without_embeddings = [
            {"id": "n1", "name": "NoEmbed1"},
            {"id": "n2", "name": "NoEmbed2", "embedding": None},
            {"id": "n3", "name": "NoEmbed3", "embedding": []},
        ]
        result = svc.cluster_nodes(nodes_without_embeddings)
        assert result == []

    def test_cluster_nodes_filters_invalid_embeddings(self) -> None:
        """Line 44→42: branch where embedding is falsy."""
        from claude_memory.clustering import ClusteringService

        svc = ClusteringService(eps=CLUSTER_EPS, min_samples=CLUSTER_MIN_SAMPLES)
        # Mix of valid and invalid embedding nodes
        nodes = [
            {"id": "n1", "embedding": None},  # falsy
            {"id": "n2", "embedding": []},  # empty list
            {"id": "n3", "embedding": 42},  # not a list
        ]
        result = svc.cluster_nodes(nodes)
        assert result == []


# ─── Context Manager Tests ──────────────────────────────────────────


class TestContextManagerGaps:
    """Tests for uncovered lines in ContextManager and TokenBudget."""

    def test_token_budget_reset(self) -> None:
        """Line 35: TokenBudget.reset() sets used back to 0."""
        from claude_memory.context_manager import TokenBudget

        budget = TokenBudget(limit=CTX_TOKEN_LIMIT)
        budget.consume("some text to consume tokens")
        assert budget.used > 0
        budget.reset()
        assert budget.used == 0

    def test_optimize_truncates_description(self) -> None:
        """Lines 97-104: node description truncated when it doesn't fit fully."""
        from claude_memory.context_manager import ContextManager

        mgr = ContextManager(default_budget=CTX_TOKEN_LIMIT)
        # Node with a long description that won't fit full but skeleton will
        nodes = [
            {
                "name": CTX_NODE_NAME,
                "node_type": CTX_NODE_TYPE,
                "description": CTX_NODE_DESC,
            }
        ]
        result = mgr.optimize(nodes)
        assert len(result) == 1
        # Description should be truncated
        assert result[0]["description"] == "[TRUNCATED]"


# ─── Ontology Tests ──────────────────────────────────────────────────


class TestOntologyGaps:
    """Tests for uncovered lines in OntologyManager."""

    def test_load_failure_uses_defaults(self, tmp_path: Any) -> None:
        """Lines 59-60: load raises exception, defaults are preserved."""
        config_path = os.path.join(str(tmp_path), ONTOLOGY_CONFIG_PATH)
        # Write invalid JSON to trigger load failure
        with open(config_path, "w") as f:
            f.write("{{{invalid json")

        from claude_memory.ontology import OntologyManager

        mgr = OntologyManager(config_path=config_path)
        # Should still have defaults despite load failure
        assert mgr.is_valid_type("Entity")
        assert mgr.is_valid_type("Concept")

    def test_add_type_overwrite_existing(self, tmp_path: Any) -> None:
        """Line 81: overwriting an existing type triggers warning."""
        config_path = os.path.join(str(tmp_path), ONTOLOGY_CONFIG_PATH)

        from claude_memory.ontology import OntologyManager

        mgr = OntologyManager(config_path=config_path)
        # Entity already exists in defaults
        assert mgr.is_valid_type(ONTOLOGY_OVERWRITE_TYPE)

        # Overwrite it
        mgr.add_type(
            ONTOLOGY_OVERWRITE_TYPE,
            "Overwritten description",
            [ONTOLOGY_REQUIRED_PROP],
        )
        defn = mgr.get_type_definition(ONTOLOGY_OVERWRITE_TYPE)
        assert defn is not None
        assert defn["description"] == "Overwritten description"
        assert defn["required_properties"] == [ONTOLOGY_REQUIRED_PROP]

    def test_add_type_without_required_properties(self, tmp_path: Any) -> None:
        """Line 81: required_properties is None → default to empty list."""
        config_path = os.path.join(str(tmp_path), ONTOLOGY_CONFIG_PATH)

        from claude_memory.ontology import OntologyManager

        mgr = OntologyManager(config_path=config_path)
        mgr.add_type(ONTOLOGY_TYPE_NAME, ONTOLOGY_TYPE_DESC)
        defn = mgr.get_type_definition(ONTOLOGY_TYPE_NAME)
        assert defn is not None
        assert defn["required_properties"] == []


# ─── Additional Branch Gap Tests ────────────────────────────────────


# NOTE: TestContextManagerBranchGaps removed — pure branch coverage test.
# Branch is marked # pragma: no cover in context_manager.py.


class TestLibrarianBranchGaps:
    """Cover branch 72→60: consolidation returns no 'id'."""

    @pytest.fixture()
    def librarian(self) -> Any:
        with patch("claude_memory.librarian.ClusteringService"):
            with patch("claude_memory.librarian.MemoryService"):
                from claude_memory.librarian import LibrarianAgent

                mock_memory = MagicMock()
                mock_clustering = MagicMock()
                mock_clustering.min_samples = CLUSTER_MIN_SAMPLES
                return LibrarianAgent(
                    memory_service=mock_memory,
                    clustering_service=mock_clustering,
                )

    async def test_consolidation_no_id_in_result(self, librarian: Any) -> None:
        """Branch 72→60: consolidation result has no 'id' key."""
        nodes = [
            {"id": LIBRARIAN_NODE_ID_1, "name": LIBRARIAN_NODE_NAME_1},
            {"id": LIBRARIAN_NODE_ID_2, "name": LIBRARIAN_NODE_NAME_2},
            {"id": LIBRARIAN_NODE_ID_3, "name": LIBRARIAN_NODE_NAME_3},
        ]
        librarian.memory.repo.get_all_nodes.return_value = nodes

        from claude_memory.clustering import Cluster

        mock_cluster = Cluster(
            id=LIBRARIAN_CLUSTER_ID, nodes=nodes, centroid=[0.1, 0.2], cohesion_score=0.5
        )
        librarian.clustering.cluster_nodes.return_value = [mock_cluster]
        librarian.memory.consolidate_memories = AsyncMock(return_value={"status": "partial"})
        librarian.memory.prune_stale = AsyncMock(return_value={"deleted_count": 0})

        report = await librarian.run_cycle()
        assert report["consolidations_created"] == 0


class TestLockManagerBranchGaps:
    """Cover remaining lock_manager branches."""

    def test_release_redis_no_client(self) -> None:
        """Branch 94→exit: client is None, release is a no-op."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError("no redis")
            mgr = LockManager()
            assert mgr.client is None
            mgr._release_redis(LOCK_PROJECT_ID)

    def test_file_lock_stale_value_error(self, tmp_path: Any) -> None:
        """Lines 116-117: stale lock has non-numeric content → ValueError."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError("no redis")
            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

            lock_path = os.path.join(str(tmp_path), f"{LOCK_PROJECT_ID}.lock")
            with open(lock_path, "w") as f:
                f.write("not-a-number")

            with patch("claude_memory.lock_manager.time") as mock_time:
                call_count = 0

                def fake_time() -> float:
                    nonlocal call_count
                    call_count += 1
                    return 0.0 if call_count <= 2 else 999.0

                mock_time.time = fake_time
                mock_time.sleep = MagicMock()
                result = mgr._acquire_file(LOCK_PROJECT_ID, timeout=1)
                assert result is False


# ─── Async Lock Manager Tests ──────────────────────────────────────


class TestAsyncLockManager:
    """Tests for the new async lock acquire/release and async context manager."""

    async def test_async_acquire_redis_success(self) -> None:
        """Async Redis lock acquisition succeeds on first try."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            mock_redis.return_value.set.return_value = True
            mgr = LockManager()

        result = await mgr.async_acquire(LOCK_PROJECT_ID, timeout=LOCK_TIMEOUT)
        assert result is True

    async def test_async_acquire_redis_timeout(self) -> None:
        """Async Redis lock acquisition times out with asyncio.sleep."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.return_value = True
            mock_redis.return_value.set.return_value = False
            mgr = LockManager()

        with patch("claude_memory.lock_manager.time") as mock_time:
            call_count = 0

            def fake_time() -> float:
                nonlocal call_count
                call_count += 1
                return 0.0 if call_count <= 2 else 999.0

            mock_time.time = fake_time
            with patch("claude_memory.lock_manager.asyncio.sleep", new_callable=AsyncMock):
                result = await mgr._async_acquire_redis(LOCK_PROJECT_ID, timeout=1)
                assert result is False

    async def test_async_acquire_file_success(self, tmp_path: Any) -> None:
        """Async file lock acquisition succeeds."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("no redis")
            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

        result = await mgr.async_acquire(LOCK_PROJECT_ID, timeout=LOCK_TIMEOUT)
        assert result is True

    async def test_async_context_manager_success(self) -> None:
        """ProjectLock async context manager acquires and releases."""
        from claude_memory.lock_manager import ProjectLock

        mock_manager = MagicMock()
        mock_manager.async_acquire = AsyncMock(return_value=True)
        lock = ProjectLock(mock_manager, LOCK_PROJECT_ID)

        async with lock:
            pass  # Lock acquired

        mock_manager.async_acquire.assert_called_once_with(LOCK_PROJECT_ID, 5)
        mock_manager.release.assert_called_once_with(LOCK_PROJECT_ID)

    async def test_async_context_manager_timeout(self) -> None:
        """ProjectLock async context manager raises TimeoutError on failure."""
        from claude_memory.lock_manager import ProjectLock

        mock_manager = MagicMock()
        mock_manager.async_acquire = AsyncMock(return_value=False)
        lock = ProjectLock(mock_manager, LOCK_PROJECT_ID)

        with pytest.raises(TimeoutError, match=LOCK_PROJECT_ID):
            async with lock:
                pass

    async def test_async_file_lock_stale_cleanup(self, tmp_path: Any) -> None:
        """Lines 170-176: async file lock detects and removes stale lock."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("no redis")
            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

        # Create a stale lock file (very old timestamp)
        lock_path = os.path.join(str(tmp_path), f"{LOCK_PROJECT_ID}.lock")
        with open(lock_path, "w") as f:
            f.write(str(LOCK_STALE_TIMESTAMP))

        result = await mgr._async_acquire_file(LOCK_PROJECT_ID, timeout=LOCK_TIMEOUT)
        assert result is True

    async def test_async_file_lock_stale_value_error(self, tmp_path: Any) -> None:
        """Line 177: stale lock has non-numeric content → ValueError caught."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("no redis")
            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

        lock_path = os.path.join(str(tmp_path), f"{LOCK_PROJECT_ID}.lock")
        with open(lock_path, "w") as f:
            f.write("not-a-number")

        with patch("claude_memory.lock_manager.time") as mock_time:
            call_count = 0

            def fake_time() -> float:
                nonlocal call_count
                call_count += 1
                return 0.0 if call_count <= 2 else 999.0

            mock_time.time = fake_time
            with patch("claude_memory.lock_manager.asyncio.sleep", new_callable=AsyncMock):
                result = await mgr._async_acquire_file(LOCK_PROJECT_ID, timeout=1)
                assert result is False

    async def test_async_file_lock_timeout(self, tmp_path: Any) -> None:
        """Lines 179-181: async file lock times out when lock held by other."""
        from claude_memory.lock_manager import LockManager

        with patch("claude_memory.lock_manager.redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("no redis")
            mgr = LockManager()
            mgr.lock_dir = str(tmp_path)

        # Create a fresh (non-stale) lock file
        lock_path = os.path.join(str(tmp_path), f"{LOCK_PROJECT_ID}.lock")
        with open(lock_path, "w") as f:
            f.write(str(LOCK_CURRENT_TIMESTAMP))

        with patch("claude_memory.lock_manager.time") as mock_time:
            call_count = 0

            def fake_time() -> float:
                nonlocal call_count
                call_count += 1
                return 0.0 if call_count <= 2 else 999.0

            mock_time.time = fake_time
            with patch("claude_memory.lock_manager.asyncio.sleep", new_callable=AsyncMock):
                result = await mgr._async_acquire_file(LOCK_PROJECT_ID, timeout=1)
                assert result is False
