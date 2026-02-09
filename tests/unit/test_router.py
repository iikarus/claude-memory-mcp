"""Tests for QueryRouter — intent classification and dispatch.

Covers:
- classify() — all 4 intents + priority ordering
- route() — dispatch to correct MemoryService method
- Strategy override via explicit intent
- Edge cases: empty query, relational with/without quoted entities
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
