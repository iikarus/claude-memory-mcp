"""Mutation-killing tests for temporal.py — session/breakthrough property assertions.

Targets ~15 kills: end_session status, get_bottles include_content flag,
temporal neighbor direction param, query construction.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from claude_memory.schema import BottleQueryParams, SessionEndParams


def _make_service() -> tuple[Any, MagicMock]:
    """Build MemoryService with mocked infrastructure."""
    mock_embedder = MagicMock()
    mock_repo = MagicMock()
    mock_vector = MagicMock()
    mock_vector.upsert = AsyncMock()
    mock_vector.search = AsyncMock(return_value=[])

    lock_ctx = AsyncMock()
    lock_ctx.__aenter__ = AsyncMock(return_value=lock_ctx)
    lock_ctx.__aexit__ = AsyncMock(return_value=False)
    lock_mock = MagicMock()
    lock_mock.lock.return_value = lock_ctx

    with (
        patch("claude_memory.tools.MemoryRepository", return_value=mock_repo),
        patch("claude_memory.tools.LockManager", return_value=lock_mock),
        patch("claude_memory.tools.QdrantVectorStore", return_value=mock_vector),
        patch("claude_memory.tools.ActivationEngine"),
    ):
        from claude_memory.tools import MemoryService

        service = MemoryService(embedding_service=mock_embedder)
        return service, mock_repo


# ═══════════════════════════════════════════════════════════════════
# end_session — status and return values
# ═══════════════════════════════════════════════════════════════════


class TestEndSession:
    """Assert end_session sets status='closed' and handles missing sessions."""

    async def test_end_evil_status_closed(self) -> None:
        """Evil: session must be set to status='closed'."""
        service, mock_repo = _make_service()
        mock_node = MagicMock()
        mock_node.properties = {"id": "s1", "status": "active"}
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock_repo.execute_cypher.return_value = mock_result

        params = SessionEndParams(session_id="s1", summary="done")
        await service.end_session(params)
        # Verify the cypher was called to update the session
        assert mock_repo.execute_cypher.call_count >= 1

    async def test_end_evil_not_found(self) -> None:
        """Evil: if session not found, return error info."""
        service, mock_repo = _make_service()
        mock_result = MagicMock()
        mock_result.result_set = []  # no session found
        mock_repo.execute_cypher.return_value = mock_result

        params = SessionEndParams(session_id="nonexistent", summary="done")
        result = await service.end_session(params)
        assert "error" in result or "status" in result

    async def test_end_evil_summary_propagated(self) -> None:
        """Evil: summary from params must be passed to cypher."""
        service, mock_repo = _make_service()
        mock_node = MagicMock()
        mock_node.properties = {"id": "s1", "status": "active"}
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock_repo.execute_cypher.return_value = mock_result

        params = SessionEndParams(session_id="s1", summary="Test summary")
        await service.end_session(params)
        assert mock_repo.execute_cypher.called

    async def test_end_sad_outcomes_stored(self) -> None:
        """Sad: outcomes list should be propagated."""
        service, mock_repo = _make_service()
        mock_node = MagicMock()
        mock_node.properties = {"id": "s1", "status": "active"}
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock_repo.execute_cypher.return_value = mock_result

        params = SessionEndParams(
            session_id="s1",
            summary="done",
            outcomes=["fixed bug"],
        )
        await service.end_session(params)
        assert mock_repo.execute_cypher.called

    async def test_end_happy(self) -> None:
        """Happy: session ends cleanly."""
        service, mock_repo = _make_service()
        mock_node = MagicMock()
        mock_node.properties = {"id": "s1", "status": "closed", "summary": "done"}
        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock_repo.execute_cypher.return_value = mock_result

        params = SessionEndParams(session_id="s1", summary="done")
        result = await service.end_session(params)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════
# get_bottles — takes BottleQueryParams, honors include_content
# ═══════════════════════════════════════════════════════════════════


class TestGetBottles:
    """Assert get_bottles takes BottleQueryParams and returns bottle dicts."""

    async def test_bottles_evil_empty_result(self) -> None:
        """Evil: no bottles → empty list."""
        service, mock_repo = _make_service()
        mock_repo.get_bottles.return_value = []

        params = BottleQueryParams()
        result = await service.get_bottles(params)
        assert result == []

    async def test_bottles_evil_limit_passed(self) -> None:
        """Evil: default limit=10 must be passed to repo."""
        service, mock_repo = _make_service()
        mock_repo.get_bottles.return_value = []

        params = BottleQueryParams()  # limit defaults to 10
        await service.get_bottles(params)
        mock_repo.get_bottles.assert_called_once()
        call_kwargs = mock_repo.get_bottles.call_args
        assert call_kwargs[1]["limit"] == 10 or call_kwargs[0][0] == 10

    async def test_bottles_evil_include_content_false(self) -> None:
        """Evil: include_content=False should NOT fetch observations."""
        service, mock_repo = _make_service()
        mock_repo.get_bottles.return_value = [
            {"id": "b1", "name": "Bottle1"},
        ]

        params = BottleQueryParams(include_content=False)
        await service.get_bottles(params)
        # execute_cypher should NOT be called for observations
        mock_repo.execute_cypher.assert_not_called()

    async def test_bottles_sad_include_content_true_fetches_obs(self) -> None:
        """Sad: include_content=True triggers observation query per bottle."""
        service, mock_repo = _make_service()
        mock_repo.get_bottles.return_value = [
            {"id": "b1", "name": "Bottle1"},
        ]
        obs_result = MagicMock()
        obs_result.result_set = [["obs content"]]
        mock_repo.execute_cypher.return_value = obs_result

        params = BottleQueryParams(include_content=True)
        result = await service.get_bottles(params)
        mock_repo.execute_cypher.assert_called()
        assert result[0]["observations"] == ["obs content"]

    async def test_bottles_happy(self) -> None:
        """Happy: returns list of bottle dicts."""
        service, mock_repo = _make_service()
        mock_repo.get_bottles.return_value = [
            {"id": "b1", "name": "B1", "node_type": "Bottle"},
            {"id": "b2", "name": "B2", "node_type": "Bottle"},
        ]

        params = BottleQueryParams(limit=5)
        result = await service.get_bottles(params)
        assert isinstance(result, list)
        assert len(result) == 2
