"""Mutation-killing tests for function signature default parameters.

Targets Pattern P4 (~40 kills): functions like get_neighbors(depth=1, limit=20, offset=0)
have defaults that mutmut mutates without any test noticing. These tests call functions
WITHOUT specifying optional args and assert the defaults are active.
"""

from __future__ import annotations

import inspect

from claude_memory.clustering import detect_gaps
from claude_memory.router import QueryRouter

# ═══════════════════════════════════════════════════════════════════
# search.py — get_neighbors defaults
# ═══════════════════════════════════════════════════════════════════


class TestGetNeighborsDefaults:
    """Assert get_neighbors default parameters: depth=1, limit=20, offset=0."""

    def test_defaults_evil_signature_depth(self) -> None:
        """Evil: depth default must be 1 in function signature."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.get_neighbors)
        assert sig.parameters["depth"].default == 1
        assert sig.parameters["depth"].default != 2

    def test_defaults_evil_signature_limit(self) -> None:
        """Evil: limit default must be 20, not 21."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.get_neighbors)
        assert sig.parameters["limit"].default == 20

    def test_defaults_evil_signature_offset(self) -> None:
        """Evil: offset default must be 0, not 1."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.get_neighbors)
        assert sig.parameters["offset"].default == 0

    def test_defaults_sad_all_have_defaults(self) -> None:
        """Sad: all optional params actually have default values."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.get_neighbors)
        for param_name in ("depth", "limit", "offset"):
            assert sig.parameters[param_name].default is not inspect.Parameter.empty

    def test_defaults_happy_all_correct(self) -> None:
        """Happy: all default values match expected."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.get_neighbors)
        assert sig.parameters["depth"].default == 1
        assert sig.parameters["limit"].default == 20
        assert sig.parameters["offset"].default == 0


# ═══════════════════════════════════════════════════════════════════
# search_advanced.py — search_associative defaults
# ═══════════════════════════════════════════════════════════════════


class TestSearchAssociativeDefaults:
    """Assert search_associative default parameters."""

    def test_defaults_evil_limit(self) -> None:
        """Evil: limit default must be 10, not 11."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.search_associative)
        assert sig.parameters["limit"].default == 10

    def test_defaults_evil_decay(self) -> None:
        """Evil: decay default must be 0.6, not 0.7."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.search_associative)
        assert sig.parameters["decay"].default == 0.6

    def test_defaults_evil_max_hops(self) -> None:
        """Evil: max_hops default must be 3, not 4."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.search_associative)
        assert sig.parameters["max_hops"].default == 3
        assert sig.parameters["max_hops"].default != 4

    def test_defaults_sad_weights_default_none(self) -> None:
        """Sad: weight params default to None (use env vars)."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.search_associative)
        for w in ("w_sim", "w_act", "w_sal", "w_rec"):
            assert sig.parameters[w].default is None

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.search_associative)
        assert sig.parameters["limit"].default == 10
        assert sig.parameters["decay"].default == 0.6
        assert sig.parameters["max_hops"].default == 3


# ═══════════════════════════════════════════════════════════════════
# search_advanced.py — get_hologram defaults
# ═══════════════════════════════════════════════════════════════════


class TestGetHologramDefaults:
    """Assert get_hologram default parameters: depth=1, max_tokens=8000."""

    def test_defaults_evil_depth(self) -> None:
        """Evil: depth default must be 1, not 2."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.get_hologram)
        assert sig.parameters["depth"].default == 1

    def test_defaults_evil_max_tokens(self) -> None:
        """Evil: max_tokens default must be 8000, not 8001."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.get_hologram)
        assert sig.parameters["max_tokens"].default == 8000

    def test_defaults_evil_max_tokens_not_zero(self) -> None:
        """Evil: max_tokens must not be 0."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.get_hologram)
        assert sig.parameters["max_tokens"].default > 0

    def test_defaults_sad_both_have_defaults(self) -> None:
        """Sad: both params have default values."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.get_hologram)
        assert sig.parameters["depth"].default is not inspect.Parameter.empty
        assert sig.parameters["max_tokens"].default is not inspect.Parameter.empty

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        from claude_memory.search_advanced import SearchAdvancedMixin

        sig = inspect.signature(SearchAdvancedMixin.get_hologram)
        assert sig.parameters["depth"].default == 1
        assert sig.parameters["max_tokens"].default == 8000


# ═══════════════════════════════════════════════════════════════════
# search.py — search defaults
# ═══════════════════════════════════════════════════════════════════


class TestSearchDefaults:
    """Assert search() default parameters."""

    def test_defaults_evil_limit(self) -> None:
        """Evil: limit default must be 5, not 10."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.search)
        assert sig.parameters["limit"].default == 5

    def test_defaults_evil_offset(self) -> None:
        """Evil: offset default must be 0."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.search)
        assert sig.parameters["offset"].default == 0

    def test_defaults_evil_mmr_false(self) -> None:
        """Evil: mmr default must be False."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.search)
        assert sig.parameters["mmr"].default is False

    def test_defaults_sad_strategy_none(self) -> None:
        """Sad: strategy defaults to None (direct vector search)."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.search)
        assert sig.parameters["strategy"].default is None

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        from claude_memory.search import SearchMixin

        sig = inspect.signature(SearchMixin.search)
        assert sig.parameters["limit"].default == 5
        assert sig.parameters["offset"].default == 0
        assert sig.parameters["mmr"].default is False
        assert sig.parameters["strategy"].default is None
        assert sig.parameters["deep"].default is False


# ═══════════════════════════════════════════════════════════════════
# clustering.py — detect_gaps defaults
# ═══════════════════════════════════════════════════════════════════


class TestDetectGapsDefaults:
    """Assert detect_gaps default parameters."""

    def test_defaults_evil_min_similarity(self) -> None:
        """Evil: min_similarity default must be 0.7."""
        sig = inspect.signature(detect_gaps)
        assert sig.parameters["min_similarity"].default == 0.7

    def test_defaults_evil_max_edges(self) -> None:
        """Evil: max_edges default must be 2, not 3."""
        sig = inspect.signature(detect_gaps)
        assert sig.parameters["max_edges"].default == 2
        assert sig.parameters["max_edges"].default != 3

    def test_defaults_evil_not_zero(self) -> None:
        """Evil: defaults must not be zero."""
        sig = inspect.signature(detect_gaps)
        assert sig.parameters["min_similarity"].default > 0

    def test_defaults_sad_both_have_values(self) -> None:
        """Sad: both params have explicit defaults."""
        sig = inspect.signature(detect_gaps)
        assert sig.parameters["min_similarity"].default is not inspect.Parameter.empty
        assert sig.parameters["max_edges"].default is not inspect.Parameter.empty

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        sig = inspect.signature(detect_gaps)
        assert sig.parameters["min_similarity"].default == 0.7
        assert sig.parameters["max_edges"].default == 2


# ═══════════════════════════════════════════════════════════════════
# router.py — route() defaults
# ═══════════════════════════════════════════════════════════════════


class TestRouteDefaults:
    """Assert QueryRouter.route() default parameters."""

    def test_defaults_evil_limit(self) -> None:
        """Evil: limit default must be 10, not 11."""
        sig = inspect.signature(QueryRouter.route)
        assert sig.parameters["limit"].default == 10

    def test_defaults_evil_intent_none(self) -> None:
        """Evil: intent default must be None (auto-classify)."""
        sig = inspect.signature(QueryRouter.route)
        assert sig.parameters["intent"].default is None

    def test_defaults_evil_project_id_none(self) -> None:
        """Evil: project_id default must be None."""
        sig = inspect.signature(QueryRouter.route)
        assert sig.parameters["project_id"].default is None

    def test_defaults_sad_all_optional(self) -> None:
        """Sad: intent, limit, project_id all have defaults."""
        sig = inspect.signature(QueryRouter.route)
        for p in ("intent", "limit", "project_id"):
            assert sig.parameters[p].default is not inspect.Parameter.empty

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        sig = inspect.signature(QueryRouter.route)
        assert sig.parameters["limit"].default == 10
        assert sig.parameters["intent"].default is None
        assert sig.parameters["project_id"].default is None


# ═══════════════════════════════════════════════════════════════════
# temporal.py — get_temporal_neighbors defaults
# ═══════════════════════════════════════════════════════════════════


class TestTemporalNeighborsDefaults:
    """Assert get_temporal_neighbors default parameters."""

    def test_defaults_evil_direction(self) -> None:
        """Evil: direction default must be 'both', not 'forward' or 'reverse'."""
        from claude_memory.temporal import TemporalMixin

        sig = inspect.signature(TemporalMixin.get_temporal_neighbors)
        assert sig.parameters["direction"].default == "both"

    def test_defaults_evil_limit(self) -> None:
        """Evil: limit default must be 10, not 11."""
        from claude_memory.temporal import TemporalMixin

        sig = inspect.signature(TemporalMixin.get_temporal_neighbors)
        assert sig.parameters["limit"].default == 10

    def test_defaults_evil_direction_not_mutated(self) -> None:
        """Evil: mutmut-style mutation to 'XXbothXX' must not match."""
        from claude_memory.temporal import TemporalMixin

        sig = inspect.signature(TemporalMixin.get_temporal_neighbors)
        assert sig.parameters["direction"].default != "XXbothXX"

    def test_defaults_sad_all_have_values(self) -> None:
        """Sad: optional params have defaults."""
        from claude_memory.temporal import TemporalMixin

        sig = inspect.signature(TemporalMixin.get_temporal_neighbors)
        for p in ("direction", "limit"):
            assert sig.parameters[p].default is not inspect.Parameter.empty

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        from claude_memory.temporal import TemporalMixin

        sig = inspect.signature(TemporalMixin.get_temporal_neighbors)
        assert sig.parameters["direction"].default == "both"
        assert sig.parameters["limit"].default == 10


# ═══════════════════════════════════════════════════════════════════
# tools_extra.py — function defaults
# ═══════════════════════════════════════════════════════════════════


class TestToolsExtraDefaults:
    """Assert tools_extra function default parameter values."""

    def test_search_assoc_evil_limit(self) -> None:
        """Evil: search_associative limit default must be 10."""
        from claude_memory.tools_extra import search_associative

        sig = inspect.signature(search_associative)
        assert sig.parameters["limit"].default == 10

    def test_search_assoc_evil_decay(self) -> None:
        """Evil: search_associative decay default must be 0.6."""
        from claude_memory.tools_extra import search_associative

        sig = inspect.signature(search_associative)
        assert sig.parameters["decay"].default == 0.6

    def test_search_assoc_evil_max_hops(self) -> None:
        """Evil: search_associative max_hops default must be 3."""
        from claude_memory.tools_extra import search_associative

        sig = inspect.signature(search_associative)
        assert sig.parameters["max_hops"].default == 3

    def test_query_timeline_sad_limit(self) -> None:
        """Sad: query_timeline limit default must be 20."""
        from claude_memory.tools_extra import query_timeline

        sig = inspect.signature(query_timeline)
        assert sig.parameters["limit"].default == 20

    def test_tools_extra_happy_all_defaults(self) -> None:
        """Happy: all tools_extra function defaults verified."""
        from claude_memory.tools_extra import (
            find_knowledge_gaps,
            get_bottles,
            get_temporal_neighbors,
            reconnect,
            search_associative,
        )

        # search_associative
        sig = inspect.signature(search_associative)
        assert sig.parameters["limit"].default == 10
        assert sig.parameters["decay"].default == 0.6
        assert sig.parameters["max_hops"].default == 3

        # get_temporal_neighbors
        sig = inspect.signature(get_temporal_neighbors)
        assert sig.parameters["direction"].default == "both"
        assert sig.parameters["limit"].default == 10

        # get_bottles
        sig = inspect.signature(get_bottles)
        assert sig.parameters["limit"].default == 10
        assert sig.parameters["include_content"].default is False

        # find_knowledge_gaps
        sig = inspect.signature(find_knowledge_gaps)
        assert sig.parameters["min_similarity"].default == 0.7
        assert sig.parameters["max_edges"].default == 2
        assert sig.parameters["limit"].default == 10

        # reconnect
        sig = inspect.signature(reconnect)
        assert sig.parameters["limit"].default == 10


# ═══════════════════════════════════════════════════════════════════
# graph_algorithms.py — compute_pagerank defaults
# ═══════════════════════════════════════════════════════════════════


class TestPageRankDefaults:
    """Assert compute_pagerank default parameters."""

    def test_defaults_evil_damping(self) -> None:
        """Evil: damping default must be 0.85, not 0.86."""
        from claude_memory.graph_algorithms import compute_pagerank

        sig = inspect.signature(compute_pagerank)
        assert sig.parameters["damping"].default == 0.85

    def test_defaults_evil_iterations(self) -> None:
        """Evil: iterations default must be 20, not 21."""
        from claude_memory.graph_algorithms import compute_pagerank

        sig = inspect.signature(compute_pagerank)
        assert sig.parameters["iterations"].default == 20

    def test_defaults_evil_not_zero(self) -> None:
        """Evil: defaults must not be zero."""
        from claude_memory.graph_algorithms import compute_pagerank

        sig = inspect.signature(compute_pagerank)
        assert sig.parameters["damping"].default > 0
        assert sig.parameters["iterations"].default > 0

    def test_defaults_sad_reasonable_range(self) -> None:
        """Sad: damping in (0, 1), iterations > 0."""
        from claude_memory.graph_algorithms import compute_pagerank

        sig = inspect.signature(compute_pagerank)
        assert 0 < sig.parameters["damping"].default < 1
        assert sig.parameters["iterations"].default > 0

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        from claude_memory.graph_algorithms import compute_pagerank

        sig = inspect.signature(compute_pagerank)
        assert sig.parameters["damping"].default == 0.85
        assert sig.parameters["iterations"].default == 20


# ═══════════════════════════════════════════════════════════════════
# activation.py — defaults (if in scope)
# ═══════════════════════════════════════════════════════════════════


class TestActivationDefaults:
    """Assert ActivationEngine default parameters."""

    def test_defaults_evil_spread_decay(self) -> None:
        """Evil: spread() decay default must be 0.6."""
        from claude_memory.activation import ActivationEngine

        sig = inspect.signature(ActivationEngine.spread)
        assert sig.parameters["decay"].default == 0.6

    def test_defaults_evil_spread_max_hops(self) -> None:
        """Evil: spread() max_hops default must be 3."""
        from claude_memory.activation import ActivationEngine

        sig = inspect.signature(ActivationEngine.spread)
        assert sig.parameters["max_hops"].default == 3

    def test_defaults_evil_not_mutated(self) -> None:
        """Evil: defaults must not be off-by-one."""
        from claude_memory.activation import ActivationEngine

        sig = inspect.signature(ActivationEngine.spread)
        assert sig.parameters["decay"].default != 0.7
        assert sig.parameters["max_hops"].default != 4

    def test_defaults_sad_decay_in_range(self) -> None:
        """Sad: decay must be between 0 and 1."""
        from claude_memory.activation import ActivationEngine

        sig = inspect.signature(ActivationEngine.spread)
        assert 0 < sig.parameters["decay"].default < 1

    def test_defaults_happy(self) -> None:
        """Happy: all defaults correct."""
        from claude_memory.activation import ActivationEngine

        sig = inspect.signature(ActivationEngine.spread)
        assert sig.parameters["decay"].default == 0.6
        assert sig.parameters["max_hops"].default == 3
