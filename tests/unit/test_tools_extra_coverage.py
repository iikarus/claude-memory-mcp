"""Tests for tools_extra.py — coverage gap remediation.

Covers the thin runtime-registered MCP tool functions:
  - query_timeline
  - get_temporal_neighbors
  - get_bottles
  - graph_health
  - find_knowledge_gaps
  - reconnect
  - system_diagnostics
  - list_orphans
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from claude_memory import tools_extra

# ─── Helpers ────────────────────────────────────────────────────────


def _patch_service(method_name: str, return_value: object = None) -> AsyncMock:
    """Create an AsyncMock for a service method and patch it."""
    mock = AsyncMock(return_value=return_value)
    return mock


# ═══════════════════════════════════════════════════════════════
#  query_timeline
# ═══════════════════════════════════════════════════════════════


class TestQueryTimeline:
    """3e/1s/1h for query_timeline."""

    @pytest.mark.asyncio()
    async def test_happy_returns_entities(self) -> None:
        """Happy: query_timeline proxies to service and returns results."""
        mock_svc = AsyncMock()
        mock_svc.query_timeline.return_value = [{"id": "e1"}]
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.query_timeline("2026-01-01", "2026-12-31")
        assert result == [{"id": "e1"}]

    @pytest.mark.asyncio()
    async def test_happy_with_project_filter(self) -> None:
        """Happy: passes project_id filter through."""
        mock_svc = AsyncMock()
        mock_svc.query_timeline.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.query_timeline(
                "2026-01-01", "2026-12-31", project_id="proj-1"
            )
        assert result == []

    @pytest.mark.asyncio()
    async def test_sad_empty_results(self) -> None:
        """Sad: no entities in time window returns empty list."""
        mock_svc = AsyncMock()
        mock_svc.query_timeline.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.query_timeline("2099-01-01", "2099-12-31")
        assert result == []

    @pytest.mark.asyncio()
    async def test_evil_invalid_date_raises(self) -> None:
        """Evil: non-ISO date string raises ValueError."""
        mock_svc = AsyncMock()
        with patch.object(tools_extra, "_service", mock_svc):
            with pytest.raises(ValueError):
                await tools_extra.query_timeline("not-a-date", "2026-12-31")

    @pytest.mark.asyncio()
    async def test_evil_service_failure_propagates(self) -> None:
        """Evil: service exceptions propagate to caller (LOUD path)."""
        mock_svc = AsyncMock()
        mock_svc.query_timeline.side_effect = ConnectionError("DB down")
        with patch.object(tools_extra, "_service", mock_svc):
            with pytest.raises(ConnectionError):
                await tools_extra.query_timeline("2026-01-01", "2026-12-31")

    @pytest.mark.asyncio()
    async def test_evil_reversed_dates_accepted(self) -> None:
        """Evil: end before start is accepted (DB handles semantics)."""
        mock_svc = AsyncMock()
        mock_svc.query_timeline.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.query_timeline("2026-12-31", "2026-01-01")
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  get_temporal_neighbors
# ═══════════════════════════════════════════════════════════════


class TestGetTemporalNeighbors:
    """3e/1s/1h for get_temporal_neighbors."""

    @pytest.mark.asyncio()
    async def test_happy_returns_neighbors(self) -> None:
        """Happy: returns temporal neighbors."""
        mock_svc = AsyncMock()
        mock_svc.get_temporal_neighbors.return_value = [{"id": "n1"}]
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.get_temporal_neighbors("entity-1")
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_sad_no_neighbors(self) -> None:
        """Sad: isolated entity returns empty list."""
        mock_svc = AsyncMock()
        mock_svc.get_temporal_neighbors.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.get_temporal_neighbors("isolated")
        assert result == []

    @pytest.mark.asyncio()
    async def test_evil_service_error_propagates(self) -> None:
        """Evil: service error is not swallowed."""
        mock_svc = AsyncMock()
        mock_svc.get_temporal_neighbors.side_effect = RuntimeError("boom")
        with patch.object(tools_extra, "_service", mock_svc):
            with pytest.raises(RuntimeError):
                await tools_extra.get_temporal_neighbors("e1")


# ═══════════════════════════════════════════════════════════════
#  get_bottles
# ═══════════════════════════════════════════════════════════════


class TestGetBottles:
    """3e/1s/1h for get_bottles."""

    @pytest.mark.asyncio()
    async def test_happy_basic(self) -> None:
        """Happy: returns bottles with defaults."""
        mock_svc = AsyncMock()
        mock_svc.get_bottles.return_value = [{"id": "b1"}]
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.get_bottles()
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_happy_all_filters(self) -> None:
        """Happy: all optional parameters forwarded."""
        mock_svc = AsyncMock()
        mock_svc.get_bottles.return_value = [{"id": "b2"}]
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.get_bottles(
                search_text="reflection",
                before_date="2026-12-31T00:00:00",
                after_date="2026-01-01T00:00:00",
                project_id="proj-1",
                include_content=True,
            )
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_sad_no_bottles(self) -> None:
        """Sad: no bottles found."""
        mock_svc = AsyncMock()
        mock_svc.get_bottles.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.get_bottles()
        assert result == []

    @pytest.mark.asyncio()
    async def test_evil_bad_date_format_raises(self) -> None:
        """Evil: non-ISO before_date raises ValueError."""
        mock_svc = AsyncMock()
        with patch.object(tools_extra, "_service", mock_svc):
            with pytest.raises(ValueError):
                await tools_extra.get_bottles(before_date="not-a-date")


# ═══════════════════════════════════════════════════════════════
#  graph_health, find_knowledge_gaps, reconnect, system_diagnostics, list_orphans
# ═══════════════════════════════════════════════════════════════


class TestGraphHealth:
    """Tests for graph_health."""

    @pytest.mark.asyncio()
    async def test_happy_returns_metrics(self) -> None:
        """Happy: returns health dict."""
        mock_svc = AsyncMock()
        mock_svc.get_graph_health.return_value = {"total_nodes": 100}
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.graph_health()
        assert result["total_nodes"] == 100


class TestFindKnowledgeGaps:
    """Tests for find_knowledge_gaps."""

    @pytest.mark.asyncio()
    async def test_happy_returns_gaps(self) -> None:
        """Happy: returns gap list."""
        mock_svc = AsyncMock()
        mock_svc.detect_structural_gaps.return_value = [{"pair": "a-b"}]
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.find_knowledge_gaps()
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_sad_no_gaps(self) -> None:
        """Sad: no gaps returns empty list."""
        mock_svc = AsyncMock()
        mock_svc.detect_structural_gaps.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.find_knowledge_gaps()
        assert result == []


class TestReconnect:
    """Tests for reconnect."""

    @pytest.mark.asyncio()
    async def test_happy_returns_briefing(self) -> None:
        """Happy: returns session briefing."""
        mock_svc = AsyncMock()
        mock_svc.reconnect.return_value = {"recent": [], "health": {}}
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.reconnect(project_id="proj-1")
        assert "recent" in result


class TestSystemDiagnostics:
    """Tests for system_diagnostics."""

    @pytest.mark.asyncio()
    async def test_happy_returns_diagnostics(self) -> None:
        """Happy: returns diagnostics dict."""
        mock_svc = AsyncMock()
        mock_svc.system_diagnostics.return_value = {"graph": {}, "vector": {}}
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.system_diagnostics()
        assert "graph" in result


class TestListOrphans:
    """Tests for list_orphans."""

    @pytest.mark.asyncio()
    async def test_happy_returns_orphans(self) -> None:
        """Happy: returns orphan list."""
        mock_svc = AsyncMock()
        mock_svc.list_orphans.return_value = [{"id": "o1"}]
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.list_orphans()
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_sad_no_orphans(self) -> None:
        """Sad: no orphans returns empty list."""
        mock_svc = AsyncMock()
        mock_svc.list_orphans.return_value = []
        with patch.object(tools_extra, "_service", mock_svc):
            result = await tools_extra.list_orphans()
        assert result == []
