"""Tests for QueryRouter — intent classification and dispatch.

Covers:
- classify() — all 4 intents + priority ordering
- route() — dispatch to correct MemoryService method
- Strategy override via explicit intent
- Edge cases: empty query, relational with/without quoted entities
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.router import QueryIntent, QueryRouter

# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def router() -> QueryRouter:
    """Fresh QueryRouter instance."""
    return QueryRouter()


@pytest.fixture()
def mock_service() -> MagicMock:
    """MemoryService with all methods mocked."""
    svc = MagicMock()
    svc.search = AsyncMock(return_value=[{"id": "sem-1"}])
    svc.search_associative = AsyncMock(return_value=[{"id": "assoc-1"}])
    svc.query_timeline = AsyncMock(return_value=[{"id": "temp-1"}])
    svc.traverse_path = AsyncMock(return_value=[{"id": "rel-1"}])
    return svc


# ─── classify() tests ──────────────────────────────────────────────


class TestClassify:
    """Tests for QueryRouter.classify()."""

    def test_empty_query_returns_semantic(self, router: QueryRouter) -> None:
        """Empty query defaults to SEMANTIC."""
        assert router.classify("") == QueryIntent.SEMANTIC

    def test_plain_query_returns_semantic(self, router: QueryRouter) -> None:
        """Plain factual query defaults to SEMANTIC."""
        assert router.classify("what is Python") == QueryIntent.SEMANTIC

    @pytest.mark.parametrize(
        "query",
        [
            "when did we discuss authentication",
            "show me the timeline of changes",
            "what happened last week",
            "show recent memory",
            "what's the chronological order",
            "history of the project",
        ],
    )
    def test_temporal_queries(self, router: QueryRouter, query: str) -> None:
        """Temporal keywords trigger TEMPORAL intent."""
        assert router.classify(query) == QueryIntent.TEMPORAL

    @pytest.mark.parametrize(
        "query",
        [
            'what connects "auth" to "database"',
            "path between the two modules",
            "what is the relationship between X and Y",
        ],
    )
    def test_relational_queries(self, router: QueryRouter, query: str) -> None:
        """Relational keywords trigger RELATIONAL intent."""
        assert router.classify(query) == QueryIntent.RELATIONAL

    @pytest.mark.parametrize(
        "query",
        [
            "what is associated with the auth module",
            "things related to Python patterns",
            "similar to the caching design",
            "in the context of microservices",
        ],
    )
    def test_associative_queries(self, router: QueryRouter, query: str) -> None:
        """Associative keywords trigger ASSOCIATIVE intent."""
        assert router.classify(query) == QueryIntent.ASSOCIATIVE

    def test_temporal_takes_priority_over_relational(self, router: QueryRouter) -> None:
        """TEMPORAL wins when both temporal and relational keywords present."""
        assert router.classify("when was the connection between X and Y") == QueryIntent.TEMPORAL

    def test_relational_takes_priority_over_associative(self, router: QueryRouter) -> None:
        """RELATIONAL wins over ASSOCIATIVE."""
        assert router.classify("what connects things related to auth") == QueryIntent.RELATIONAL


# ─── route() tests ─────────────────────────────────────────────────


class TestRoute:
    """Tests for QueryRouter.route() dispatch."""

    @pytest.mark.asyncio()
    async def test_route_empty_query(self, router: QueryRouter, mock_service: MagicMock) -> None:
        """Empty query returns [] without calling any service."""
        result = await router.route("", mock_service)
        assert result == []
        mock_service.search.assert_not_called()

    @pytest.mark.asyncio()
    async def test_route_semantic(self, router: QueryRouter, mock_service: MagicMock) -> None:
        """SEMANTIC intent dispatches to search()."""
        result = await router.route("what is Python", mock_service)
        mock_service.search.assert_called_once()
        assert result == [{"id": "sem-1"}]

    @pytest.mark.asyncio()
    async def test_route_associative(self, router: QueryRouter, mock_service: MagicMock) -> None:
        """ASSOCIATIVE intent dispatches to search_associative()."""
        result = await router.route("things related to auth patterns", mock_service)
        mock_service.search_associative.assert_called_once()
        assert result == [{"id": "assoc-1"}]

    @pytest.mark.asyncio()
    async def test_route_temporal(self, router: QueryRouter, mock_service: MagicMock) -> None:
        """TEMPORAL intent dispatches to query_timeline()."""
        result = await router.route("what happened last week", mock_service)
        mock_service.query_timeline.assert_called_once()
        assert result == [{"id": "temp-1"}]

    @pytest.mark.asyncio()
    async def test_route_relational_with_quoted_entities(
        self, router: QueryRouter, mock_service: MagicMock
    ) -> None:
        """RELATIONAL with quoted entities dispatches to traverse_path()."""
        result = await router.route('what connects "auth_module" to "database_layer"', mock_service)
        mock_service.traverse_path.assert_called_once_with("auth_module", "database_layer")
        assert result == [{"id": "rel-1"}]

    @pytest.mark.asyncio()
    async def test_route_relational_fallback_to_search(
        self, router: QueryRouter, mock_service: MagicMock
    ) -> None:
        """RELATIONAL without quoted entities falls back to search()."""
        result = await router.route("what connects the modules", mock_service)
        mock_service.search.assert_called_once()
        assert result == [{"id": "sem-1"}]

    @pytest.mark.asyncio()
    async def test_explicit_intent_override(
        self, router: QueryRouter, mock_service: MagicMock
    ) -> None:
        """Explicit intent overrides auto-classification."""
        # Query looks semantic but we force ASSOCIATIVE
        result = await router.route(
            "what is Python",
            mock_service,
            intent=QueryIntent.ASSOCIATIVE,
        )
        mock_service.search_associative.assert_called_once()
        assert result == [{"id": "assoc-1"}]

    @pytest.mark.asyncio()
    async def test_route_passes_limit_and_project(
        self, router: QueryRouter, mock_service: MagicMock
    ) -> None:
        """Limit and project_id are forwarded to the underlying method."""
        await router.route("what is Python", mock_service, limit=20, project_id="proj-x")
        call_kwargs = mock_service.search.call_args
        assert call_kwargs.kwargs["limit"] == 20
        assert call_kwargs.kwargs["project_id"] == "proj-x"

    @pytest.mark.asyncio()
    async def test_route_temporal_passes_project(
        self, router: QueryRouter, mock_service: MagicMock
    ) -> None:
        """Temporal route passes project_id into TemporalQueryParams."""
        await router.route("timeline of changes", mock_service, project_id="proj-y")
        call_args = mock_service.query_timeline.call_args
        params = call_args.args[0]
        assert params.project_id == "proj-y"


# ─── QueryIntent enum tests ────────────────────────────────────────


class TestQueryIntent:
    """Tests for the QueryIntent enum."""

    def test_values(self) -> None:
        """All 4 intents have string values."""
        assert QueryIntent.SEMANTIC.value == "semantic"
        assert QueryIntent.ASSOCIATIVE.value == "associative"
        assert QueryIntent.TEMPORAL.value == "temporal"
        assert QueryIntent.RELATIONAL.value == "relational"

    def test_from_string(self) -> None:
        """Can construct from string value."""
        assert QueryIntent("semantic") == QueryIntent.SEMANTIC
        assert QueryIntent("temporal") == QueryIntent.TEMPORAL


# ─── Integration: strategy param on search() ───────────────────────

# Module-level constants for test_tools mock patches
_TOOLS_MODULE = "claude_memory.tools"
_SEARCH_ASSOC_MODULE = f"{_TOOLS_MODULE}.MemoryService.search_associative"


class TestSearchStrategy:
    """Tests for the strategy param wired through search() — ADR-007 updated."""

    @pytest.mark.asyncio()
    async def test_search_strategy_auto_logs_deprecation(self) -> None:
        """strategy='auto' logs deprecation, falls through to hybrid default."""
        svc = MagicMock()
        svc.embedder = MagicMock()
        svc.embedder.encode.return_value = [0.1]
        svc.vector_store = MagicMock()
        svc.vector_store.search = AsyncMock(return_value=[{"_id": "a", "_score": 0.9}])
        svc.router = MagicMock()
        svc.router.classify.return_value = QueryIntent.SEMANTIC
        svc.repo = MagicMock()
        svc.repo.get_subgraph.return_value = {
            "nodes": [
                {
                    "id": "a",
                    "name": "A",
                    "node_type": "Entity",
                    "project_id": "p",
                    "salience_score": 0.5,
                }
            ],
            "edges": [],
        }
        svc._fire_salience_update = MagicMock()

        # Wire internal async methods since svc is a MagicMock (not a real MemoryService)
        from claude_memory.search import SearchMixin

        svc._execute_vector_search = AsyncMock(return_value=[{"_id": "a", "_score": 0.9}])
        svc._hydrate_merged_results = AsyncMock(return_value=[])

        import logging

        # Bind the real search method's logic
        with patch.object(logging.getLogger("claude_memory.search"), "warning") as mock_warn:
            _ = await SearchMixin.search(svc, "plain query", strategy="auto")

        mock_warn.assert_called_once()
        assert "deprecated" in mock_warn.call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_search_strategy_explicit_semantic(self) -> None:
        """strategy='semantic' dispatches via _direct_strategy_search."""
        from claude_memory.schema import SearchResult

        mock_result = SearchResult(
            id="sr-2",
            name="Vec",
            node_type="Entity",
            project_id="p",
            content="c",
            score=0.8,
            distance=0.2,
        )

        svc = MagicMock()
        svc.router = MagicMock()
        svc.router.route = AsyncMock(return_value=[mock_result])

        # Wire _direct_strategy_search by calling it properly
        from claude_memory.search import SearchMixin

        svc._direct_strategy_search = AsyncMock(return_value=[mock_result])

        result = await SearchMixin.search(svc, "what is Python", strategy="semantic")
        svc._direct_strategy_search.assert_called_once()
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_search_strategy_none_uses_hybrid_pipeline(self) -> None:
        """strategy=None (default) runs hybrid pipeline with router.classify()."""
        from claude_memory.schema import SearchResult
        from claude_memory.search import SearchMixin

        mock_sr = SearchResult(
            id="a",
            name="A",
            node_type="Entity",
            project_id="p",
            score=0.9,
            distance=0.1,
        )

        svc = MagicMock()
        svc.router = MagicMock()
        svc.router.classify.return_value = QueryIntent.SEMANTIC
        svc._execute_vector_search = AsyncMock(return_value=[{"_id": "a", "_score": 0.9}])
        svc._hydrate_merged_results = AsyncMock(return_value=[mock_sr])
        svc._compute_recency = MagicMock(return_value=0.0)

        result = await SearchMixin.search(svc, "test query")

        # In ADR-007, strategy=None now uses router.classify()
        svc.router.classify.assert_called_once_with("test query")
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_search_strategy_temporal_attaches_vector_scores(self) -> None:
        """Explicit temporal strategy attaches vector scores to dict results."""
        from claude_memory.schema import SearchResult
        from claude_memory.search import SearchMixin

        mock_sr = SearchResult(
            id="d-1",
            name="Node1",
            node_type="Entity",
            project_id="p",
            score=0.75,
            distance=0.25,
            retrieval_strategy="temporal",
            vector_score=0.75,
        )

        svc = MagicMock()
        svc._direct_strategy_search = AsyncMock(return_value=[mock_sr])

        result = await SearchMixin.search(svc, "timeline of events", strategy="temporal")
        assert len(result) == 1
        assert result[0].retrieval_strategy == "temporal"

    @pytest.mark.asyncio()
    async def test_search_strategy_empty_query_returns_empty(self) -> None:
        """strategy set but empty query still returns []."""
        from claude_memory.search import SearchMixin

        svc = MagicMock()
        result = await SearchMixin.search(svc, "", strategy="auto")
        assert result == []
