"""Mutation-killing tests for dict values — service return dicts.

Split from test_mutant_dict_values.py per 300-line module cap.
Covers analysis.py, temporal.py, and librarian.py dict structures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.schema import BreakthroughParams, SessionStartParams


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
    mock_repo.get_graph_health.return_value = {
        "total_nodes": 10,
        "total_edges": 5,
        "density": 0.1,
        "orphan_nodes": 2,
        "avg_degree": 1.0,
    }
    mock_repo.get_all_nodes.return_value = []
    mock_repo.get_all_node_ids.return_value = []
    mock_repo.get_all_edges.return_value = []
    mock_repo.query_timeline.return_value = []

    mock_vector = MagicMock()
    mock_vector.upsert = AsyncMock()
    mock_vector.search = AsyncMock(return_value=[])
    mock_vector.delete = AsyncMock()
    mock_vector.count = AsyncMock(return_value=10)
    mock_vector.list_ids = AsyncMock(return_value=[])

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


class TestGraphHealth:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.l = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.l)

    async def test_evil_community_count_key(self) -> None:
        assert "community_count" in await self.svc.get_graph_health()

    async def test_evil_community_zero_few_nodes(self) -> None:
        self.r.get_graph_health.return_value = {
            "total_nodes": 1,
            "total_edges": 0,
            "density": 0.0,
            "orphan_nodes": 0,
            "avg_degree": 0.0,
        }
        assert (await self.svc.get_graph_health())["community_count"] == 0

    async def test_evil_keys_preserved(self) -> None:
        r = await self.svc.get_graph_health()
        for k in ("total_nodes", "total_edges", "density"):
            assert k in r

    async def test_sad_clustering_failure(self) -> None:
        self.r.get_graph_health.return_value = {
            "total_nodes": 100,
            "total_edges": 50,
            "density": 0.5,
            "orphan_nodes": 0,
            "avg_degree": 1.0,
        }
        self.r.get_all_nodes.side_effect = ConnectionError("boom")
        assert (await self.svc.get_graph_health())["community_count"] == 0

    async def test_happy(self) -> None:
        r = await self.svc.get_graph_health()
        assert r["total_nodes"] == 10
        assert r["total_edges"] == 5


class TestSystemDiagnostics:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.lm = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.lm)

    async def test_evil_graph_key(self) -> None:
        assert "graph" in await self.svc.system_diagnostics()

    async def test_evil_vector_key(self) -> None:
        assert "vector" in await self.svc.system_diagnostics()

    async def test_evil_split_brain_key(self) -> None:
        assert "split_brain" in await self.svc.system_diagnostics()

    async def test_sad_vector_error(self) -> None:
        self.v.count = AsyncMock(side_effect=Exception("Qdrant down"))
        r = await self.svc.system_diagnostics()
        assert r["vector"]["error"] == "Qdrant down"
        assert r["split_brain"]["status"] == "unavailable"

    async def test_happy(self) -> None:
        r = await self.svc.system_diagnostics()
        assert r["vector"]["count"] == 10
        assert r["split_brain"]["status"] == "ok"


class TestReconnect:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.lm = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.lm)

    async def test_evil_recent_entities(self) -> None:
        assert "recent_entities" in await self.svc.reconnect()

    async def test_evil_health(self) -> None:
        assert "health" in await self.svc.reconnect()

    async def test_evil_window(self) -> None:
        r = await self.svc.reconnect()
        assert "start" in r["window"]
        assert "end" in r["window"]

    async def test_sad_empty(self) -> None:
        assert (await self.svc.reconnect())["recent_entities"] == []

    async def test_happy(self) -> None:
        self.r.query_timeline.return_value = [{"name": "N1"}]
        r = await self.svc.reconnect()
        assert r["recent_entities"] == [{"name": "N1"}]


class TestStartSession:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.lm = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.lm)
        node = MagicMock()
        node.properties = {
            "id": "s1",
            "status": "active",
            "node_type": "Session",
            "project_id": "p1",
        }
        result = MagicMock()
        result.result_set = [[node]]
        self.r.execute_cypher.return_value = result

    async def test_evil_status_active(self) -> None:
        await self.svc.start_session(SessionStartParams(project_id="p1", focus="c"))
        assert self.r.execute_cypher.call_args[0][1]["props"]["status"] == "active"

    async def test_evil_node_type(self) -> None:
        await self.svc.start_session(SessionStartParams(project_id="p1", focus="c"))
        assert self.r.execute_cypher.call_args[0][1]["props"]["node_type"] == "Session"

    async def test_evil_project_id(self) -> None:
        await self.svc.start_session(SessionStartParams(project_id="my-p", focus="c"))
        assert self.r.execute_cypher.call_args[0][1]["props"]["project_id"] == "my-p"

    async def test_sad_focus(self) -> None:
        await self.svc.start_session(SessionStartParams(project_id="p1", focus="debug"))
        assert self.r.execute_cypher.call_args[0][1]["props"]["focus"] == "debug"

    async def test_happy(self) -> None:
        await self.svc.start_session(SessionStartParams(project_id="p1", focus="t"))
        props = self.r.execute_cypher.call_args[0][1]["props"]
        assert props["status"] == "active"
        assert "id" in props
        assert "created_at" in props


class TestRecordBreakthrough:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.e, self.r, self.v, self.lm = _make_mock_service()
        self.svc = _build(self.e, self.r, self.v, self.lm)

    async def test_evil_node_type(self) -> None:
        params = BreakthroughParams(name="E", moment="m", session_id="s1")
        await self.svc.record_breakthrough(params)
        t, props = self.r.create_node.call_args[0]
        assert t == "Breakthrough"
        assert props["node_type"] == "Breakthrough"

    async def test_evil_project_meta(self) -> None:
        params = BreakthroughParams(name="E", moment="m", session_id="s1")
        await self.svc.record_breakthrough(params)
        assert self.r.create_node.call_args[0][1]["project_id"] == "meta"

    async def test_evil_certainty(self) -> None:
        params = BreakthroughParams(name="E", moment="m", session_id="s1")
        await self.svc.record_breakthrough(params)
        assert self.r.create_node.call_args[0][1]["certainty"] == "confirmed"

    async def test_sad_analogy_empty(self) -> None:
        params = BreakthroughParams(name="X", moment="Y", session_id="s1")
        await self.svc.record_breakthrough(params)
        assert self.r.create_node.call_args[0][1]["analogy"] == ""

    async def test_happy_edge(self) -> None:
        params = BreakthroughParams(name="X", moment="Y", session_id="s1")
        await self.svc.record_breakthrough(params)
        assert self.r.create_edge.call_args[0][2] == "BREAKTHROUGH_IN"
        assert self.r.create_edge.call_args[0][3] == {"confidence": 1.0}


class TestLibrarianCycle:
    async def test_evil_keys(self) -> None:
        e, r, v, lm = _make_mock_service()
        svc = _build(e, r, v, lm)
        r.get_all_nodes.return_value = []
        from claude_memory.clustering import ClusteringService
        from claude_memory.librarian import LibrarianAgent

        report = await LibrarianAgent(svc, ClusteringService()).run_cycle()
        expected = (
            "clusters_found",
            "consolidations_created",
            "deleted_stale",
            "gaps_detected",
            "errors",
        )
        for k in expected:
            assert k in report

    async def test_evil_zeros(self) -> None:
        e, r, v, lm = _make_mock_service()
        svc = _build(e, r, v, lm)
        r.get_all_nodes.return_value = []
        from claude_memory.clustering import ClusteringService
        from claude_memory.librarian import LibrarianAgent

        report = await LibrarianAgent(svc, ClusteringService()).run_cycle()
        assert report["clusters_found"] == 0
        assert report["consolidations_created"] == 0

    async def test_evil_errors_list(self) -> None:
        e, r, v, lm = _make_mock_service()
        svc = _build(e, r, v, lm)
        r.get_all_nodes.return_value = []
        from claude_memory.clustering import ClusteringService
        from claude_memory.librarian import LibrarianAgent

        assert LibrarianAgent is not None  # just checking import
        report = await LibrarianAgent(svc, ClusteringService()).run_cycle()
        assert report["errors"] == []

    async def test_sad_fetch_failure(self) -> None:
        e, r, v, lm = _make_mock_service()
        svc = _build(e, r, v, lm)
        r.get_all_nodes.side_effect = ConnectionError("db down")
        from claude_memory.clustering import ClusteringService
        from claude_memory.librarian import LibrarianAgent

        report = await LibrarianAgent(svc, ClusteringService()).run_cycle()
        assert "db down" in report["errors"][0]

    async def test_happy_gap_reports(self) -> None:
        e, r, v, lm = _make_mock_service()
        svc = _build(e, r, v, lm)
        r.get_all_nodes.return_value = []
        from claude_memory.clustering import ClusteringService
        from claude_memory.librarian import LibrarianAgent

        report = await LibrarianAgent(svc, ClusteringService()).run_cycle()
        assert report["gap_reports_stored"] == 0
