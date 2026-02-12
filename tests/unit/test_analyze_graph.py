"""Tests for analyze_graph() rebuild — Phase 2 SHOULD FIX.

Verifies that analyze_graph() computes PageRank and Louvain in Python
rather than calling non-existent FalkorDB algo.* procedures.
Tests verify BEHAVIOR: given a known graph structure, the algorithms
return correct relative rankings and community groupings.
"""

from unittest.mock import MagicMock

import pytest

from claude_memory.analysis import AnalysisMixin


def _make_analysis_mixin() -> AnalysisMixin:
    """Build an AnalysisMixin with all dependencies mocked."""
    mixin = AnalysisMixin.__new__(AnalysisMixin)
    mixin.repo = MagicMock()
    mixin.embedder = MagicMock()
    mixin.vector_store = MagicMock()
    mixin.ontology = MagicMock()
    return mixin


def _make_cypher_result(rows: list[list]) -> MagicMock:
    """Create a mock Cypher query result."""
    result = MagicMock()
    result.result_set = rows
    return result


def _make_node(name: str, labels: set[str] | None = None) -> MagicMock:
    """Create a mock graph node."""
    node = MagicMock()
    node.properties = {"id": name, "name": name}
    node.labels = labels or {"Entity"}
    return node


# ─── PageRank tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pagerank_returns_ranked_entities() -> None:
    """PageRank returns entities sorted by rank, highest first."""
    mixin = _make_analysis_mixin()

    # Star topology: A<-B, A<-C, A<-D (A should have highest rank)
    node_a = _make_node("A")
    node_b = _make_node("B")
    node_c = _make_node("C")
    node_d = _make_node("D")

    # First query: get all nodes
    nodes_result = _make_cypher_result([[node_a], [node_b], [node_c], [node_d]])
    # Second query: get all edges (source_id, target_id)
    edges_result = _make_cypher_result([["B", "A"], ["C", "A"], ["D", "A"]])

    mixin.repo.execute_cypher.side_effect = [nodes_result, edges_result]

    results = await mixin.analyze_graph(algorithm="pagerank")

    assert len(results) > 0
    # A should be ranked first (most incoming links)
    assert results[0]["name"] == "A"
    assert "rank" in results[0]
    assert results[0]["rank"] > results[1]["rank"]


@pytest.mark.asyncio
async def test_pagerank_empty_graph() -> None:
    """PageRank on empty graph returns empty list."""
    mixin = _make_analysis_mixin()
    mixin.repo.execute_cypher.return_value = _make_cypher_result([])

    results = await mixin.analyze_graph(algorithm="pagerank")

    assert results == []


@pytest.mark.asyncio
async def test_pagerank_cypher_error_is_loud() -> None:
    """PageRank raises on FalkorDB errors (no silent swallowing)."""
    mixin = _make_analysis_mixin()
    mixin.repo.execute_cypher.side_effect = ConnectionError("FalkorDB down")

    with pytest.raises(ConnectionError, match="FalkorDB down"):
        await mixin.analyze_graph(algorithm="pagerank")


# ─── Louvain tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_louvain_returns_communities() -> None:
    """Louvain returns community groupings with sizes and members."""
    mixin = _make_analysis_mixin()

    # Two disconnected clusters: {A,B,C} and {D,E}
    nodes = [_make_node(n) for n in ["A", "B", "C", "D", "E"]]
    nodes_result = _make_cypher_result([[n] for n in nodes])
    # Edges within clusters only
    edges_result = _make_cypher_result(
        [
            ["A", "B"],
            ["B", "C"],
            ["A", "C"],  # cluster 1
            ["D", "E"],  # cluster 2
        ]
    )

    mixin.repo.execute_cypher.side_effect = [nodes_result, edges_result]

    results = await mixin.analyze_graph(algorithm="louvain")

    assert len(results) >= 2
    # Each community should have community_id, size, members
    for community in results:
        assert "community_id" in community
        assert "size" in community
        assert "members" in community
        assert community["size"] > 0


@pytest.mark.asyncio
async def test_louvain_empty_graph() -> None:
    """Louvain on empty graph returns empty list."""
    mixin = _make_analysis_mixin()
    mixin.repo.execute_cypher.return_value = _make_cypher_result([])

    results = await mixin.analyze_graph(algorithm="louvain")

    assert results == []


@pytest.mark.asyncio
async def test_louvain_cypher_error_is_loud() -> None:
    """Louvain raises on FalkorDB errors (no silent swallowing)."""
    mixin = _make_analysis_mixin()
    mixin.repo.execute_cypher.side_effect = ConnectionError("FalkorDB down")

    with pytest.raises(ConnectionError, match="FalkorDB down"):
        await mixin.analyze_graph(algorithm="louvain")
