"""Tests for list_orphans tool — 3-evil / 1-sad / 1-happy + 1 scenario.

Covers the full count→list→act triad inspection layer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Module Import (patch infra before import) ──────────────────────

with patch("claude_memory.repository.FalkorDB"):
    with patch("claude_memory.lock_manager.redis.Redis"):
        with patch("claude_memory.vector_store.AsyncQdrantClient"):
            from claude_memory import tools_extra


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def mock_service():
    """Create a mock MemoryService with list_orphans wired."""
    svc = MagicMock()
    svc.list_orphans = AsyncMock()
    tools_extra._service = svc
    yield svc
    tools_extra._service = None


# ─── Happy Path ─────────────────────────────────────────────────────


@pytest.mark.asyncio()
async def test_returns_orphan_nodes(mock_service):
    """Graph with 3 orphans → returns 3 dicts with all fields."""
    mock_service.list_orphans.return_value = [
        {
            "id": "aaa-111",
            "name": "Python",
            "node_type": "Entity",
            "project_id": "proj-a",
            "focus": None,
            "labels": ["Entity"],
            "created_at": "2026-01-01T00:00:00",
        },
        {
            "id": "bbb-222",
            "name": "Session-X",
            "node_type": "Session",
            "project_id": "proj-b",
            "focus": "refactoring",
            "labels": ["Session"],
            "created_at": "2026-01-02T00:00:00",
        },
        {
            "id": "ccc-333",
            "name": "Observation-Y",
            "node_type": "Observation",
            "project_id": "proj-a",
            "focus": None,
            "labels": ["Observation"],
            "created_at": "2026-01-03T00:00:00",
        },
    ]

    result = await tools_extra.list_orphans(limit=50)

    assert len(result) == 3
    assert result[0]["id"] == "aaa-111"
    assert result[0]["node_type"] == "Entity"
    assert result[1]["project_id"] == "proj-b"
    assert result[2]["labels"] == ["Observation"]
    mock_service.list_orphans.assert_awaited_once_with(limit=50)


# ─── Sad Path ───────────────────────────────────────────────────────


@pytest.mark.asyncio()
async def test_empty_graph_returns_empty(mock_service):
    """No nodes at all → returns empty list."""
    mock_service.list_orphans.return_value = []

    result = await tools_extra.list_orphans()

    assert result == []
    mock_service.list_orphans.assert_awaited_once_with(limit=50)


# ─── Evil Paths ─────────────────────────────────────────────────────


@pytest.mark.asyncio()
async def test_limit_zero_returns_empty(mock_service):
    """limit=0 → boundary case, returns empty list."""
    mock_service.list_orphans.return_value = []

    result = await tools_extra.list_orphans(limit=0)

    assert result == []
    mock_service.list_orphans.assert_awaited_once_with(limit=0)


@pytest.mark.asyncio()
async def test_connected_nodes_excluded(mock_service):
    """Service only returns unconnected nodes — connected ones never appear."""
    # The repo query uses WHERE NOT (n)--(), so connected nodes are filtered
    # at the Cypher level. We verify the tool passes through faithfully.
    mock_service.list_orphans.return_value = [
        {
            "id": "orphan-1",
            "name": "Alone",
            "node_type": "Entity",
            "project_id": "proj-a",
            "focus": None,
            "labels": ["Entity"],
            "created_at": "2026-03-01T00:00:00",
        },
    ]

    result = await tools_extra.list_orphans(limit=100)

    assert len(result) == 1
    assert result[0]["name"] == "Alone"


@pytest.mark.asyncio()
async def test_self_loop_not_orphan(mock_service):
    """Node with self-loop (n)-[:REL]->(n) has a relationship → not returned."""
    # Self-loops mean (n)--() is true, so Cypher excludes them.
    # Service returns empty if the only node has a self-loop.
    mock_service.list_orphans.return_value = []

    result = await tools_extra.list_orphans()

    assert result == []


# ─── Scenario: Nameless Session Orphan ──────────────────────────────


@pytest.mark.asyncio()
async def test_nameless_orphan_returns_focus(mock_service):
    """Session nodes with no name but a focus property still return useful data.

    This is the exact scenario hit during manual Dragon Brain inspection —
    orphan Sessions had no name but had focus='architecture review'.
    """
    mock_service.list_orphans.return_value = [
        {
            "id": "sess-999",
            "name": None,
            "node_type": "Session",
            "project_id": "frankenlearn",
            "focus": "architecture review",
            "labels": ["Session"],
            "created_at": "2026-03-09T00:30:00",
        },
    ]

    result = await tools_extra.list_orphans(limit=10)

    assert len(result) == 1
    assert result[0]["name"] is None
    assert result[0]["focus"] == "architecture review"
    assert result[0]["project_id"] == "frankenlearn"
    mock_service.list_orphans.assert_awaited_once_with(limit=10)
