"""Mutation-killing tests for router.py — keywords, QueryIntent, classification.

Split from test_mutant_schema_integrity.py per 300-line module cap.
"""

from __future__ import annotations

import pytest

from claude_memory.router import (
    _ASSOCIATIVE_KEYWORDS,
    _MIN_QUOTED_ENTITIES,
    _RELATIONAL_KEYWORDS,
    _TEMPORAL_KEYWORDS,
    QueryIntent,
    QueryRouter,
)

_EXPECTED_TEMPORAL = [
    "when",
    "timeline",
    "chronolog",
    "history of",
    "last week",
    "last month",
    "yesterday",
    "before",
    "after",
    "recent",
    "earliest",
    "latest",
    "over time",
    "sequence",
]

_EXPECTED_RELATIONAL = [
    "connect",
    "path between",
    "link between",
    "bridge",
    "relationship between",
    "how does .+ relate to",
    "what connects",
]

_EXPECTED_ASSOCIATIVE = [
    "associated with",
    "related to",
    "similar to",
    "reminds me of",
    "in the context of",
    "neighbourhood of",
    "neighborhood of",
    "cluster around",
    "spreading",
]


class TestRouterKeywords:
    """Assert exact keyword lists."""

    def test_temporal_evil_mutated_absent(self) -> None:
        """Evil: mutated keywords must not be present."""
        assert "XXwhenXX" not in _TEMPORAL_KEYWORDS
        assert "XXtimelineXX" not in _TEMPORAL_KEYWORDS

    def test_temporal_evil_count_exact(self) -> None:
        """Evil: exactly 14 temporal keywords."""
        assert len(_TEMPORAL_KEYWORDS) == 14

    def test_temporal_evil_each_keyword(self) -> None:
        """Evil: every keyword at correct position."""
        for i, kw in enumerate(_EXPECTED_TEMPORAL):
            assert _TEMPORAL_KEYWORDS[i] == kw

    def test_temporal_sad_partial_not_present(self) -> None:
        """Sad: substring that isn't a keyword shouldn't match."""
        assert "time" not in _TEMPORAL_KEYWORDS

    def test_temporal_happy(self) -> None:
        """Happy: all expected temporal keywords present."""
        assert _TEMPORAL_KEYWORDS == _EXPECTED_TEMPORAL

    def test_relational_evil_count(self) -> None:
        """Evil: exactly 7 relational keywords."""
        assert len(_RELATIONAL_KEYWORDS) == 7

    def test_relational_evil_each_keyword(self) -> None:
        """Evil: every keyword at correct position."""
        for i, kw in enumerate(_EXPECTED_RELATIONAL):
            assert _RELATIONAL_KEYWORDS[i] == kw

    def test_relational_evil_mutated_absent(self) -> None:
        """Evil: mutated keywords not present."""
        assert "XXconnectXX" not in _RELATIONAL_KEYWORDS

    def test_relational_sad_similar_not_present(self) -> None:
        """Sad: similar string is not the keyword."""
        assert "linked between" not in _RELATIONAL_KEYWORDS

    def test_relational_happy(self) -> None:
        """Happy: all expected relational keywords present."""
        assert _RELATIONAL_KEYWORDS == _EXPECTED_RELATIONAL

    def test_associative_evil_count(self) -> None:
        """Evil: exactly 9 associative keywords."""
        assert len(_ASSOCIATIVE_KEYWORDS) == 9

    def test_associative_evil_each_keyword(self) -> None:
        """Evil: every keyword at correct position."""
        for i, kw in enumerate(_EXPECTED_ASSOCIATIVE):
            assert _ASSOCIATIVE_KEYWORDS[i] == kw

    def test_associative_evil_mutated_absent(self) -> None:
        """Evil: mutated keywords not present."""
        assert "XXspreakingXX" not in _ASSOCIATIVE_KEYWORDS

    def test_associative_sad_both_spellings(self) -> None:
        """Sad: both UK and US spellings present."""
        assert "neighbourhood of" in _ASSOCIATIVE_KEYWORDS
        assert "neighborhood of" in _ASSOCIATIVE_KEYWORDS

    def test_associative_happy(self) -> None:
        """Happy: all expected associative keywords present."""
        assert _ASSOCIATIVE_KEYWORDS == _EXPECTED_ASSOCIATIVE


class TestQueryIntent:
    """Assert QueryIntent enum values."""

    def test_intent_evil_mutated_value(self) -> None:
        """Evil: enum values must be exact strings."""
        assert QueryIntent.SEMANTIC.value == "semantic"
        assert QueryIntent.TEMPORAL.value == "temporal"

    def test_intent_evil_extra_member(self) -> None:
        """Evil: no extra members beyond the expected 4."""
        assert len(QueryIntent) == 4

    def test_intent_evil_values_lowercase(self) -> None:
        """Evil: all values must be lowercase strings."""
        for intent in QueryIntent:
            assert intent.value == intent.value.lower()
            assert intent.value.isalpha()

    def test_intent_sad_unknown_not_valid(self) -> None:
        """Sad: 'unknown' is not a valid intent."""
        with pytest.raises(ValueError):
            QueryIntent("unknown")

    def test_intent_happy_all_values(self) -> None:
        """Happy: all 4 intents present with correct values."""
        assert set(QueryIntent) == {
            QueryIntent.SEMANTIC,
            QueryIntent.ASSOCIATIVE,
            QueryIntent.TEMPORAL,
            QueryIntent.RELATIONAL,
        }


class TestRouterClassification:
    """Assert classification dispatches to correct intent."""

    def test_classify_evil_empty(self) -> None:
        assert QueryRouter().classify("") == QueryIntent.SEMANTIC

    def test_classify_evil_gibberish(self) -> None:
        assert QueryRouter().classify("asdf jkl qwerty") == QueryIntent.SEMANTIC

    def test_classify_evil_partial_keyword(self) -> None:
        assert QueryRouter().classify("show me recent items") == QueryIntent.TEMPORAL

    def test_classify_sad_ambiguous(self) -> None:
        assert QueryRouter().classify("when did they connect") == QueryIntent.TEMPORAL

    def test_classify_happy_temporal(self) -> None:
        r = QueryRouter()
        assert r.classify("what happened last month") == QueryIntent.TEMPORAL
        assert r.classify("show the timeline") == QueryIntent.TEMPORAL
        assert r.classify("yesterday's events") == QueryIntent.TEMPORAL

    def test_classify_happy_relational(self) -> None:
        r = QueryRouter()
        assert r.classify("path between A and B") == QueryIntent.RELATIONAL
        assert r.classify("what connects these") == QueryIntent.RELATIONAL

    def test_classify_happy_associative(self) -> None:
        r = QueryRouter()
        assert r.classify("things related to AI") == QueryIntent.ASSOCIATIVE
        assert r.classify("cluster around this") == QueryIntent.ASSOCIATIVE

    def test_classify_happy_semantic_fallback(self) -> None:
        assert QueryRouter().classify("tell me about neural networks") == QueryIntent.SEMANTIC


class TestRouterConstants:
    """Assert module-level constants in router.py."""

    def test_min_quoted_evil_not_zero(self) -> None:
        assert _MIN_QUOTED_ENTITIES > 0

    def test_min_quoted_evil_not_mutated(self) -> None:
        assert _MIN_QUOTED_ENTITIES != 3

    def test_min_quoted_evil_not_one(self) -> None:
        assert _MIN_QUOTED_ENTITIES != 1

    def test_min_quoted_sad_is_int(self) -> None:
        assert isinstance(_MIN_QUOTED_ENTITIES, int)

    def test_min_quoted_happy(self) -> None:
        assert _MIN_QUOTED_ENTITIES == 2
