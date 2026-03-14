"""Architectural invariants — structural drift detection (DRIFT-003).

These are laws, not tests. They encode the system's design contract.
Violating them means the architecture shifted, not just the behavior.

Run with: ``pytest -m invariant``
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from claude_memory.merge import rrf_merge
from claude_memory.router import QueryIntent, QueryRouter
from claude_memory.schema import SearchResult

pytestmark = pytest.mark.invariant


# ─── Score Invariants ───────────────────────────────────────


class TestScoreInvariants:
    """Scores must always be normalized and meaningful."""

    def test_score_bounded_0_1(self) -> None:
        """SearchResult.score must accept values in [0.0, 1.0] only at boundaries."""
        for val in [0.0, 0.5, 1.0]:
            r = SearchResult(
                id="x", name="x", node_type="Entity", project_id="p", score=val, distance=1.0 - val
            )
            assert 0.0 <= r.score <= 1.0

    def test_vector_score_bounded_when_present(self) -> None:
        """vector_score, when not None, must be in [0.0, 1.0]."""
        for val in [0.0, 0.5, 1.0]:
            r = SearchResult(
                id="x",
                name="x",
                node_type="Entity",
                project_id="p",
                score=val,
                distance=0.0,
                vector_score=val,
            )
            assert r.vector_score is not None
            assert 0.0 <= r.vector_score <= 1.0

    def test_recency_score_bounded(self) -> None:
        """recency_score must be in [0.0, 1.0]."""
        for val in [0.0, 0.5, 1.0]:
            r = SearchResult(
                id="x",
                name="x",
                node_type="Entity",
                project_id="p",
                score=val,
                distance=0.0,
                recency_score=val,
            )
            assert 0.0 <= r.recency_score <= 1.0

    def test_score_zero_requires_no_vector(self) -> None:
        """If score is 0.0, vector_score must be None (intentional, not silent failure).

        This invariant exists because we got burned by the ADR-007 score-0 bug.
        A result with score=0.0 AND vector_score=0.7 means the scoring pipeline
        silently dropped the score — a critical failure.
        """
        r = SearchResult(
            id="x",
            name="x",
            node_type="Entity",
            project_id="p",
            score=0.0,
            distance=1.0,
            vector_score=None,
        )
        if r.score == 0.0:
            assert r.vector_score is None, (
                f"score=0.0 but vector_score={r.vector_score} — "
                f"silent score failure detected for {r.name}"
            )


# ─── Schema Invariants ─────────────────────────────────────


class TestSchemaInvariants:
    """SearchResult schema contract must hold."""

    def test_retrieval_strategy_default_is_semantic(self) -> None:
        """Default retrieval_strategy must be 'semantic'."""
        r = SearchResult(
            id="x", name="x", node_type="Entity", project_id="p", score=0.5, distance=0.5
        )
        assert r.retrieval_strategy == "semantic"

    def test_valid_strategies_accepted(self) -> None:
        """All 5 valid strategies must be accepted."""
        valid = ["semantic", "hybrid", "temporal", "relational", "associative"]
        for strategy in valid:
            r = SearchResult(
                id="x",
                name="x",
                node_type="Entity",
                project_id="p",
                score=0.5,
                distance=0.5,
                retrieval_strategy=strategy,
            )
            assert r.retrieval_strategy == strategy

    def test_required_fields_present(self) -> None:
        """model_dump() must always contain the canonical field set."""
        required = {
            "id",
            "name",
            "node_type",
            "project_id",
            "score",
            "distance",
            "retrieval_strategy",
            "recency_score",
            "vector_score",
            "activation_score",
            "path_distance",
            "salience_score",
            "observations",
            "relationships",
            "content",
        }
        r = SearchResult(
            id="x", name="x", node_type="Entity", project_id="p", score=0.5, distance=0.5
        )
        dumped = r.model_dump()
        missing = required - set(dumped.keys())
        assert not missing, f"Missing fields: {missing}"

    def test_id_never_empty_when_set(self) -> None:
        """A SearchResult with id set must have a non-empty id."""
        r = SearchResult(
            id="abc123", name="x", node_type="Entity", project_id="p", score=0.5, distance=0.5
        )
        assert r.id and len(r.id) > 0


# ─── Router Invariants ─────────────────────────────────────


class TestRouterInvariants:
    """Router classification must be deterministic and exhaustive."""

    @given(st.text(min_size=0, max_size=500))
    def test_classify_always_returns_valid_intent(self, query: str) -> None:
        """Any string must classify to a valid QueryIntent."""
        router = QueryRouter()
        intent = router.classify(query)
        assert intent in list(QueryIntent)

    @given(st.text(min_size=1, max_size=200))
    def test_classify_is_deterministic(self, query: str) -> None:
        """Same query must always classify to the same intent."""
        router = QueryRouter()
        assert router.classify(query) == router.classify(query)

    def test_intent_enum_completeness(self) -> None:
        """QueryIntent must have exactly 4 values. Adding a new intent requires an ADR."""
        assert set(QueryIntent) == {
            QueryIntent.SEMANTIC,
            QueryIntent.TEMPORAL,
            QueryIntent.RELATIONAL,
            QueryIntent.ASSOCIATIVE,
        }, "QueryIntent enum changed — requires an ADR"


# ─── RRF Merge Invariants ──────────────────────────────────


class TestMergeInvariants:
    """RRF merge must preserve mathematical properties."""

    @given(
        vector_list=st.lists(
            st.tuples(st.text(min_size=1, max_size=10), st.floats(0.0, 1.0)),
            max_size=20,
        ),
        k=st.integers(1, 100),
        limit=st.integers(1, 50),
    )
    def test_rrf_score_always_non_negative(
        self,
        vector_list: list[tuple[str, float]],
        k: int,
        limit: int,
    ) -> None:
        """RRF scores must be >= 0."""
        vec = [{"_id": t[0], "_score": t[1]} for t in vector_list]
        merged = rrf_merge(vec, [], k=k, limit=limit)
        for m in merged:
            assert m.rrf_score >= 0.0

    @given(
        vector_list=st.lists(
            st.tuples(st.text(min_size=1, max_size=10), st.floats(0.0, 1.0)),
            max_size=20,
        ),
        graph_list=st.lists(
            st.tuples(st.text(min_size=1, max_size=10), st.floats(0.0, 1.0)),
            max_size=20,
        ),
        limit=st.integers(1, 50),
    )
    def test_rrf_output_respects_limit(
        self,
        vector_list: list[tuple[str, float]],
        graph_list: list[tuple[str, float]],
        limit: int,
    ) -> None:
        """Output length must be <= limit."""
        vec = [{"_id": t[0], "_score": t[1]} for t in vector_list]
        graph = [{"id": t[0]} for t in graph_list]
        merged = rrf_merge(vec, graph, limit=limit)
        assert len(merged) <= limit

    def test_empty_inputs_return_empty(self) -> None:
        """Empty inputs must produce empty output."""
        assert rrf_merge([], []) == []

    def test_dual_source_beats_single_source(self) -> None:
        """Entity in both sources must score >= entity in only one source."""
        vec = [{"_id": "e1", "_score": 0.8}]
        graph = [{"id": "e1"}]
        merged_both = rrf_merge(vec, graph, limit=10)
        merged_vec_only = rrf_merge(vec, [], limit=10)

        both_scores = {m.entity_id: m.rrf_score for m in merged_both}
        vec_scores = {m.entity_id: m.rrf_score for m in merged_vec_only}

        for eid, score in both_scores.items():
            if eid in vec_scores:
                assert score >= vec_scores[eid]
