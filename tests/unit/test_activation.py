"""Tests for the ActivationEngine — spreading activation retrieval."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from claude_memory.activation import ActivationEngine


def _make_engine(subgraph: dict | None = None) -> ActivationEngine:
    """Create an ActivationEngine with a mocked repository."""
    repo = MagicMock()
    repo.get_subgraph.return_value = subgraph or {"nodes": [], "edges": []}
    return ActivationEngine(repo=repo)


# ── activate() ──────────────────────────────────────────────────────


def test_activate_single_seed() -> None:
    engine = _make_engine()
    result = engine.activate(["a"])
    assert result == {"a": 1.0}


def test_activate_multiple_seeds() -> None:
    engine = _make_engine()
    result = engine.activate(["a", "b", "c"])
    assert result == {"a": 1.0, "b": 1.0, "c": 1.0}


def test_activate_custom_energy() -> None:
    engine = _make_engine()
    result = engine.activate(["x"], initial_energy=0.5)
    assert result == {"x": 0.5}


def test_activate_empty_seeds() -> None:
    engine = _make_engine()
    result = engine.activate([])
    assert result == {}


# ── spread() ────────────────────────────────────────────────────────


def test_spread_no_neighbors() -> None:
    """Seed with no edges returns only the seed."""
    engine = _make_engine({"nodes": [{"id": "a"}], "edges": []})
    seeds = {"a": 1.0}
    result = engine.spread(seeds, decay=0.6, max_hops=3)
    assert result == {"a": 1.0}


def test_spread_one_hop() -> None:
    """Energy decays by factor on direct neighbors."""
    subgraph = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
        ],
    }
    engine = _make_engine(subgraph)
    seeds = {"a": 1.0}
    result = engine.spread(seeds, decay=0.5, max_hops=1)
    assert result["a"] == 1.0
    assert result["b"] == 0.5
    assert result["c"] == 0.5


def test_spread_two_hops_decay_compounds() -> None:
    """Energy decays multiplicatively over 2 hops: decay^2."""
    # Hop 1: a -> b (energy 0.6), Hop 2: b -> c (energy 0.36)
    subgraph_hop1 = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b"}],
    }
    subgraph_hop2 = {
        "nodes": [{"id": "b"}, {"id": "c"}],
        "edges": [{"source": "b", "target": "c"}],
    }

    engine = _make_engine()
    engine.repo.get_subgraph.side_effect = [
        subgraph_hop1,
        subgraph_hop2,
        {"nodes": [], "edges": []},
    ]

    seeds = {"a": 1.0}
    result = engine.spread(seeds, decay=0.6, max_hops=3)

    assert result["a"] == 1.0
    assert abs(result["b"] - 0.6) < 1e-9
    assert abs(result["c"] - 0.36) < 1e-9


def test_spread_lateral_inhibition() -> None:
    """Only top-K nodes by energy propagate to the next hop."""
    # Create edges from 'a' to 5 nodes, but set lateral_inhibition_k=2
    edges = [{"source": "a", "target": f"n{i}"} for i in range(5)]
    subgraph = {
        "nodes": [{"id": "a"}] + [{"id": f"n{i}"} for i in range(5)],
        "edges": edges,
    }
    # Second hop: only top-2 nodes should have been queried
    engine = _make_engine()
    empty_subgraph = {"nodes": [], "edges": []}
    engine.repo.get_subgraph.side_effect = [subgraph, empty_subgraph]

    seeds = {"a": 1.0}
    result = engine.spread(seeds, decay=0.6, max_hops=2, lateral_inhibition_k=2)

    # All 5 neighbors should have received energy in hop 1
    for i in range(5):
        assert f"n{i}" in result

    # In the second call to get_subgraph, only 2 IDs should have been passed
    second_call_ids = engine.repo.get_subgraph.call_args_list[1][0][0]
    assert len(second_call_ids) == 2


def test_spread_accumulation() -> None:
    """Node reachable via 2 paths accumulates energy from both."""
    # a -> c (0.6) and b -> c (0.6), so c should get 1.2
    subgraph = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"source": "a", "target": "c"},
            {"source": "b", "target": "c"},
        ],
    }
    engine = _make_engine(subgraph)
    seeds = {"a": 1.0, "b": 1.0}
    result = engine.spread(seeds, decay=0.6, max_hops=1)

    assert abs(result["c"] - 1.2) < 1e-9


def test_spread_empty_activation() -> None:
    engine = _make_engine()
    result = engine.spread({})
    assert result == {}


# ── rank() ──────────────────────────────────────────────────────────


def test_rank_composite_score() -> None:
    """Verify the weighted merging formula."""
    now = datetime.now(UTC).isoformat()
    candidates = [
        {"id": "a", "occurred_at": now},
        {"id": "b", "occurred_at": now},
    ]
    vector_scores = {"a": 0.9, "b": 0.5}
    activation_scores = {"a": 0.3, "b": 1.0}  # b has higher activation
    salience_scores = {"a": 0.8, "b": 0.2}

    engine = _make_engine()
    ranked = engine.rank(candidates, vector_scores, activation_scores, salience_scores)

    assert len(ranked) == 2
    assert "composite_score" in ranked[0]
    # 'a' should rank higher: 0.9*0.4 + 0.3*0.3 + 0.8*0.2 + ~1.0*0.1 = ~0.72
    # 'b': 0.5*0.4 + 1.0*0.3 + 0.2*0.2 + ~1.0*0.1 = ~0.64
    assert ranked[0]["id"] == "a"


def test_rank_empty_candidates() -> None:
    engine = _make_engine()
    result = engine.rank([], {}, {}, {})
    assert result == []


def test_rank_missing_scores_default_to_zero() -> None:
    """Entities not in score dicts get 0 for that component."""
    candidates = [{"id": "x"}]
    engine = _make_engine()
    ranked = engine.rank(candidates, {}, {}, {})
    assert len(ranked) == 1
    assert ranked[0]["composite_score"] == 0.0


# ── _recency_score() ───────────────────────────────────────────────


def test_recency_score_recent_entity() -> None:
    """An entity created right now should score close to 1.0."""
    now = datetime.now(UTC).isoformat()
    score = ActivationEngine._recency_score({"occurred_at": now})
    assert score > 0.99


def test_recency_score_old_entity() -> None:
    """An entity from 90 days ago should score much lower."""
    old = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    score = ActivationEngine._recency_score({"created_at": old})
    # 2^(-90/30) = 2^(-3) = 0.125
    assert abs(score - 0.125) < 0.01


def test_recency_score_no_timestamp() -> None:
    score = ActivationEngine._recency_score({})
    assert score == 0.0


def test_recency_score_invalid_timestamp() -> None:
    score = ActivationEngine._recency_score({"occurred_at": "not-a-date"})
    assert score == 0.0
