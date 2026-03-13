"""Tests for RRF merge algorithm — ADR-007 §10.1.

3-evil/1-sad/1-happy for rrf_merge() + spec checklist coverage.
"""

from __future__ import annotations

import pytest

from claude_memory.merge import rrf_merge

# ─── Helpers ────────────────────────────────────────────────────────


def _vec(*ids: str) -> list[dict]:
    """Build mock vector results with descending scores."""
    return [{"_id": eid, "_score": 0.9 - i * 0.1} for i, eid in enumerate(ids)]


def _graph(*ids: str) -> list[dict]:
    """Build mock graph results with metadata."""
    return [{"id": eid, "name": f"Node-{eid}", "recency": 0.8} for eid in ids]


# ─── rrf_merge: 3-evil / 1-sad / 1-happy ───────────────────────────


class TestRrfMerge:
    """RRF merge algorithm tests."""

    # 🟢 Happy: two overlapping lists → overlapping entities score higher
    def test_happy_overlapping_entities_score_higher(self) -> None:
        """Entities present in both lists get higher RRF score than single-source."""
        vector = _vec("a", "b", "c")
        graph = _graph("b", "c", "d")

        merged = rrf_merge(vector, graph, k=60)

        scores = {m.entity_id: m.rrf_score for m in merged}
        # b and c appear in both → higher scores
        assert scores["b"] > scores["a"]  # a is vector-only
        assert scores["c"] > scores["d"]  # d is graph-only

    # 😢 Sad: empty graph list → vector results unchanged
    def test_sad_empty_graph_returns_vector_unchanged(self) -> None:
        """When graph results are empty, vector results pass through as-is."""
        vector = _vec("a", "b")

        merged = rrf_merge(vector, [], k=60)

        assert len(merged) == 2
        assert merged[0].entity_id == "a"
        assert merged[0].vector_score == pytest.approx(0.9)
        assert merged[0].retrieval_sources == ["vector"]
        assert merged[0].graph_rank is None

    # 😈 Evil 1: empty vector list → graph-only RRF scores
    def test_evil_empty_vector_returns_graph_only(self) -> None:
        """When vector results are empty, graph results get RRF scores."""
        graph = _graph("x", "y")

        merged = rrf_merge([], graph, k=60)

        assert len(merged) == 2
        assert merged[0].entity_id == "x"
        assert merged[0].vector_score is None
        assert merged[0].vector_rank is None
        assert merged[0].retrieval_sources == ["graph"]
        assert merged[0].rrf_score > 0

    # 😈 Evil 2: two identical lists → scores = 2/(k+rank), order preserved
    def test_evil_identical_lists_double_score(self) -> None:
        """Identical lists produce 2/(k+rank) per entity."""
        items = ["a", "b", "c"]
        vector = _vec(*items)
        graph = [{"id": eid, "_score": 0.0} for eid in items]

        merged = rrf_merge(vector, graph, k=60)

        # First entity: rank=1 in both → 2 * 1/(60+1)
        expected_score = 2.0 / (60 + 1)
        assert merged[0].entity_id == "a"
        assert merged[0].rrf_score == pytest.approx(expected_score)
        # Order preserved (rank 1 in both = highest)
        assert [m.entity_id for m in merged] == ["a", "b", "c"]

    # 😈 Evil 3: disjoint lists → all entities present, single-source scores lower
    def test_evil_disjoint_lists_all_present(self) -> None:
        """Completely disjoint lists: all entities appear, each with single-source score."""
        vector = _vec("a", "b")
        graph = _graph("x", "y")

        merged = rrf_merge(vector, graph, k=60)

        ids = {m.entity_id for m in merged}
        assert ids == {"a", "b", "x", "y"}

        # All are single-source: score = 1/(k+rank)
        for m in merged:
            assert len(m.retrieval_sources) == 1


# ─── Spec §10.1 checklist additions ────────────────────────────────


class TestRrfMergeChecklist:
    """Additional coverage from spec §10.1 table."""

    def test_k_parameter_affects_distribution(self) -> None:
        """Higher k = flatter score distribution."""
        vector = _vec("a", "b", "c")
        graph = _graph("a", "b", "c")

        merged_low_k = rrf_merge(vector, graph, k=1)
        merged_high_k = rrf_merge(vector, graph, k=1000)

        # With low k, the gap between rank-1 and rank-3 is larger
        spread_low = merged_low_k[0].rrf_score - merged_low_k[2].rrf_score
        spread_high = merged_high_k[0].rrf_score - merged_high_k[2].rrf_score
        assert spread_low > spread_high

    def test_respects_limit(self) -> None:
        """Output length never exceeds limit."""
        vector = _vec("a", "b", "c", "d", "e")
        graph = _graph("f", "g", "h", "i", "j")

        merged = rrf_merge(vector, graph, limit=3)

        assert len(merged) <= 3

    def test_both_lists_empty(self) -> None:
        """Both lists empty → empty output."""
        assert rrf_merge([], []) == []

    def test_graph_entries_without_id_skipped(self) -> None:
        """Graph entries missing 'id' key are silently skipped."""
        vector = _vec("a")
        graph = [{"name": "orphan"}]  # no 'id' key

        merged = rrf_merge(vector, graph)

        assert len(merged) == 1
        assert merged[0].entity_id == "a"

    def test_merged_result_fields_populated(self) -> None:
        """MergedResult carries all provenance information."""
        vector = [{"_id": "e1", "_score": 0.85}]
        graph = [{"id": "e1", "name": "Node-e1", "path_len": 2}]

        merged = rrf_merge(vector, graph, k=60)

        assert len(merged) == 1
        m = merged[0]
        assert m.entity_id == "e1"
        assert m.vector_score == pytest.approx(0.85)
        assert m.vector_rank == 1
        assert m.graph_rank == 1
        assert m.graph_metadata == {"name": "Node-e1", "path_len": 2}
        assert "vector" in m.retrieval_sources
        assert "graph" in m.retrieval_sources
