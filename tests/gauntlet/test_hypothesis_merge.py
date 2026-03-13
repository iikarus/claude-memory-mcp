"""Hypothesis property tests for merge.py (RRF) — Gauntlet R3.

Property-based tests for Reciprocal Rank Fusion merge:
- Score monotonicity: adding sources never decreases score
- Idempotence: merging a list with itself produces stable output
- Limit cap: output never exceeds requested limit
- Score positivity: RRF scores are always > 0
- Dual-source boost: appearing in both lists scores higher than either alone
- Determinism: same inputs always produce same outputs
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from claude_memory.merge import MergedResult, rrf_merge

FUZZ_EXAMPLES = 2000

# ═══════════════════════════════════════════════════════════════
#  Strategies
# ═══════════════════════════════════════════════════════════════

# Entity IDs: short alphanumeric strings
entity_ids = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    min_size=1,
    max_size=20,
)

# Vector result dicts: {_id: str, _score: float}
vector_result = st.fixed_dictionaries(
    {"_id": entity_ids, "_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False)},
)

# Graph result dicts: {id: str, name: str}
graph_result = st.fixed_dictionaries(
    {"id": entity_ids, "name": st.text(min_size=1, max_size=30)},
)

# Lists of results (1-20 items)
vector_list = st.lists(vector_result, min_size=0, max_size=20)
graph_list = st.lists(graph_result, min_size=0, max_size=20)

# Valid k values
k_values = st.integers(min_value=1, max_value=200)


# ═══════════════════════════════════════════════════════════════
#  RRF Merge Properties
# ═══════════════════════════════════════════════════════════════


class TestRRFMergeProperties:
    """Property tests for rrf_merge — Gauntlet R3."""

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list, k_values)
    def test_output_never_exceeds_limit(self, vec, graph, k):
        """P1: Output length ≤ limit for any input size."""
        limit = 5
        merged = rrf_merge(vec, graph, k=k, limit=limit)
        assert len(merged) <= limit

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list, k_values)
    def test_all_scores_positive(self, vec, graph, k):
        """P2: Every RRF score is strictly positive (1/(k+rank) > 0)."""
        merged = rrf_merge(vec, graph, k=k)
        for m in merged:
            assert m.rrf_score > 0

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list, k_values)
    def test_output_sorted_descending(self, vec, graph, k):
        """P3: Output is always sorted by rrf_score descending."""
        merged = rrf_merge(vec, graph, k=k)
        scores = [m.rrf_score for m in merged]
        assert scores == sorted(scores, reverse=True)

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list)
    def test_deterministic(self, vec, graph):
        """P4: Same inputs always produce identical outputs."""
        a = rrf_merge(vec, graph)
        b = rrf_merge(vec, graph)
        assert [(m.entity_id, m.rrf_score) for m in a] == [(m.entity_id, m.rrf_score) for m in b]

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list, k_values)
    def test_all_results_are_merged_result(self, vec, graph, k):
        """P5: Return type is always list[MergedResult]."""
        merged = rrf_merge(vec, graph, k=k)
        for m in merged:
            assert isinstance(m, MergedResult)

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list)
    def test_entity_ids_subset_of_inputs(self, vec, graph):
        """P6: Every entity_id in output appeared in at least one input."""
        input_ids = {v["_id"] for v in vec} | {g["id"] for g in graph}
        merged = rrf_merge(vec, graph)
        output_ids = {m.entity_id for m in merged}
        assert output_ids <= input_ids

    @settings(max_examples=500, deadline=None)
    @given(entity_ids, k_values)
    def test_dual_source_scores_higher(self, eid, k):
        """P7: Entity in both lists has higher RRF score than either alone."""
        both = rrf_merge(
            [{"_id": eid, "_score": 0.9}],
            [{"id": eid, "name": "X"}],
            k=k,
        )
        vec_only = rrf_merge(
            [{"_id": eid, "_score": 0.9}],
            [],
            k=k,
        )
        graph_only = rrf_merge(
            [],
            [{"id": eid, "name": "X"}],
            k=k,
        )

        both_score = both[0].rrf_score if both else 0
        vec_score = vec_only[0].rrf_score if vec_only else 0
        graph_score = graph_only[0].rrf_score if graph_only else 0

        assert both_score > vec_score
        assert both_score > graph_score

    @settings(max_examples=500, deadline=None)
    @given(entity_ids)
    def test_retrieval_sources_accurate(self, eid):
        """P8: retrieval_sources correctly tracks which lists contained the entity."""
        merged = rrf_merge(
            [{"_id": eid, "_score": 0.5}],
            [{"id": eid, "name": "X"}],
        )
        assert len(merged) == 1
        assert "vector" in merged[0].retrieval_sources
        assert "graph" in merged[0].retrieval_sources

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list, graph_list)
    def test_vector_score_preserved_for_vector_hits(self, vec, graph):
        """P9: vector_score is set for entities that appeared in vector_results."""
        merged = rrf_merge(vec, graph)
        vec_ids = {v["_id"] for v in vec}
        for m in merged:
            if m.entity_id in vec_ids:
                assert m.vector_score is not None

    @settings(max_examples=FUZZ_EXAMPLES, deadline=None)
    @given(vector_list)
    def test_empty_graph_list_produces_vector_only(self, vec):
        """P10: Empty graph list → all results from vector only."""
        merged = rrf_merge(vec, [])
        for m in merged:
            assert "vector" in m.retrieval_sources
            assert "graph" not in m.retrieval_sources
