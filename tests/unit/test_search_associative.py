"""Tests for search_associative() and configurable score weights.

Covers:
- Full pipeline: vector search → activation spread → composite rank
- Empty query / no vector results → early return
- Project-scoped search filter
- Per-query weight overrides
- Environment variable weight overrides
- MCP tool wrapper (search_associative in server.py)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Constants ──────────────────────────────────────────────────────

PROJECT_ID = "project-alpha"
MOCK_EMBEDDING = [0.1, 0.2, 0.3]
NOW_ISO = datetime.now(UTC).isoformat()


# ─── Module Imports (patch external deps) ───────────────────────────

with patch("claude_memory.repository.FalkorDB"):
    with patch("claude_memory.lock_manager.redis.Redis"):
        with patch("claude_memory.vector_store.AsyncQdrantClient"):
            from claude_memory.tools import MemoryService


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def service() -> MemoryService:
    """MemoryService with all deps mocked."""
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = MOCK_EMBEDDING

    with patch("claude_memory.repository.FalkorDB"):
        with patch("claude_memory.lock_manager.redis.Redis"):
            with patch("claude_memory.vector_store.AsyncQdrantClient"):
                svc = MemoryService(embedding_service=mock_embedder)

    svc.repo = MagicMock()
    svc.activation_engine.repo = svc.repo  # sync so spread() uses same mock
    svc.vector_store = AsyncMock()
    return svc


def _vector_results(*ids: str) -> list[dict[str, Any]]:
    """Build mock vector search results."""
    return [{"_id": eid, "_score": 0.9 - i * 0.1} for i, eid in enumerate(ids)]


def _graph_nodes(*ids: str) -> dict[str, Any]:
    """Build mock subgraph response for depth=0."""
    return {
        "nodes": [
            {
                "id": eid,
                "name": f"Node-{eid}",
                "node_type": "Entity",
                "project_id": PROJECT_ID,
                "salience_score": 0.5,
                "occurred_at": NOW_ISO,
            }
            for eid in ids
        ],
        "edges": [],
    }


# ─── search_associative() tests ────────────────────────────────────


@pytest.mark.asyncio()
async def test_search_associative_empty_query(service: MemoryService) -> None:
    """Empty query returns empty list immediately."""
    result = await service.search_associative("")
    assert result == []
    service.vector_store.search.assert_not_called()


@pytest.mark.asyncio()
async def test_search_associative_no_vector_hits(service: MemoryService) -> None:
    """No vector results → empty list."""
    service.vector_store.search.return_value = []
    result = await service.search_associative("hello world")
    assert result == []


@pytest.mark.asyncio()
async def test_search_associative_full_pipeline(service: MemoryService) -> None:
    """Full pipeline: seeds → spread → rank → SearchResult list."""
    service.vector_store.search.return_value = _vector_results("a", "b")

    # With max_hops=1: spread makes 1 get_subgraph call, then hydrate makes 1
    service.repo.get_subgraph.side_effect = [
        # Spread hop 1: a connects to c
        {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [{"source": "a", "target": "c"}],
        },
        # Hydrate call (depth=0): full node properties
        _graph_nodes("a", "b", "c"),
    ]

    results = await service.search_associative("test query", limit=10, max_hops=1)
    assert len(results) > 0
    assert results[0].score > 0  # composite_score mapped to score
    assert results[0].name.startswith("Node-")


@pytest.mark.asyncio()
async def test_search_associative_project_filter(service: MemoryService) -> None:
    """Project filter is passed through to vector search."""
    service.vector_store.search.return_value = _vector_results("a")
    service.repo.get_subgraph.return_value = _graph_nodes("a")

    await service.search_associative("q", project_id="proj-x")

    call_kwargs = service.vector_store.search.call_args
    assert call_kwargs.kwargs.get("filter") == {"project_id": "proj-x"}


@pytest.mark.asyncio()
async def test_search_associative_per_query_weights(service: MemoryService) -> None:
    """Per-query weight overrides change ranking scores."""
    service.vector_store.search.return_value = _vector_results("a")
    service.repo.get_subgraph.return_value = _graph_nodes("a")

    # All weight on similarity
    results_sim = await service.search_associative("q", w_sim=1.0, w_act=0.0, w_sal=0.0, w_rec=0.0)

    service.vector_store.search.return_value = _vector_results("a")
    service.repo.get_subgraph.return_value = _graph_nodes("a")

    # All weight on recency
    results_rec = await service.search_associative("q", w_sim=0.0, w_act=0.0, w_sal=0.0, w_rec=1.0)

    # Scores should differ because the inputs differ
    assert results_sim[0].score != results_rec[0].score


# ─── Configurable weight tests (env vars) ──────────────────────────


def test_rank_env_var_override() -> None:
    """SCORE_WEIGHT_* env vars override default weights."""
    from claude_memory.activation import ActivationEngine

    repo = MagicMock()
    engine = ActivationEngine(repo=repo)

    candidates = [{"id": "x", "occurred_at": NOW_ISO}]
    vector_scores = {"x": 1.0}
    activation_scores = {"x": 1.0}
    salience_scores = {"x": 1.0}

    env_overrides = {
        "SCORE_WEIGHT_SIMILARITY": "1.0",
        "SCORE_WEIGHT_ACTIVATION": "0.0",
        "SCORE_WEIGHT_SALIENCE": "0.0",
        "SCORE_WEIGHT_RECENCY": "0.0",
    }

    with patch.dict("os.environ", env_overrides):
        ranked = engine.rank(candidates, vector_scores, activation_scores, salience_scores)

    # With w_sim=1.0 and others=0, score should be exactly 1.0
    assert ranked[0]["composite_score"] == 1.0


def test_rank_per_query_overrides_env_var() -> None:
    """Per-query weights take precedence over env vars."""
    from claude_memory.activation import ActivationEngine

    repo = MagicMock()
    engine = ActivationEngine(repo=repo)

    candidates = [{"id": "x", "occurred_at": NOW_ISO}]
    vector_scores = {"x": 1.0}
    activation_scores = {"x": 1.0}
    salience_scores = {"x": 1.0}

    # Env says all weight on similarity
    env_overrides = {
        "SCORE_WEIGHT_SIMILARITY": "1.0",
        "SCORE_WEIGHT_ACTIVATION": "0.0",
        "SCORE_WEIGHT_SALIENCE": "0.0",
        "SCORE_WEIGHT_RECENCY": "0.0",
    }

    # But per-query says all weight on activation
    with patch.dict("os.environ", env_overrides):
        ranked = engine.rank(
            candidates,
            vector_scores,
            activation_scores,
            salience_scores,
            w_sim=0.0,
            w_act=1.0,
            w_sal=0.0,
            w_rec=0.0,
        )

    # activation_score of 1.0, normalized to 1.0 (max=1.0), so score = 1.0
    assert ranked[0]["composite_score"] == 1.0


def test_rank_default_weights_no_env() -> None:
    """Without env vars, defaults to 0.4/0.3/0.2/0.1."""
    from claude_memory.activation import ActivationEngine

    repo = MagicMock()
    engine = ActivationEngine(repo=repo)

    candidates = [{"id": "x", "occurred_at": NOW_ISO}]
    # Set all scores to 1.0 so composite = sum of weights = 1.0
    ranked = engine.rank(
        candidates,
        {"x": 1.0},
        {"x": 1.0},
        {"x": 1.0},
    )

    # Recency for a just-now entity ≈ 1.0, so total ≈ 1.0
    assert ranked[0]["composite_score"] > 0.99


# ─── MCP tool wrapper test ─────────────────────────────────────────


@pytest.mark.asyncio()
async def test_mcp_search_associative_no_results() -> None:
    """MCP wrapper returns 'No results found.' when empty."""
    with (
        patch("claude_memory.tools_extra._service") as mock_svc,
    ):
        mock_svc.search_associative = AsyncMock(return_value=[])
        from claude_memory.server import search_associative as mcp_search

        result = await mcp_search("hello")
        assert result == [{"message": "No results found."}]


@pytest.mark.asyncio()
async def test_mcp_search_associative_with_results() -> None:
    """MCP wrapper returns model_dump() list."""
    from claude_memory.schema import SearchResult

    mock_result = SearchResult(
        id="a",
        name="Test",
        node_type="Entity",
        project_id="p1",
        score=0.9,
        distance=0.1,
    )

    with patch("claude_memory.tools_extra._service") as mock_svc:
        mock_svc.search_associative = AsyncMock(return_value=[mock_result])
        from claude_memory.server import search_associative as mcp_search

        result = await mcp_search("hello")
        assert isinstance(result, list)
        assert result[0]["id"] == "a"
        assert result[0]["score"] == 0.9
