"""Mutation-killing tests for schema.py — Pydantic model default values.

Split from test_mutant_schema_integrity.py per 300-line module cap.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from claude_memory.schema import (
    BaseNode,
    BottleQueryParams,
    BreakthroughParams,
    EntityCommitReceipt,
    EntityCreateParams,
    EntityDeleteParams,
    EntityUpdateParams,
    GapDetectionParams,
    ObservationParams,
    RelationshipCreateParams,
    SearchResult,
    SessionEndParams,
    TemporalQueryParams,
)


class TestEntityCreateDefaults:
    """Assert EntityCreateParams default values."""

    def test_evil_certainty_not_mutated(self) -> None:
        """Evil: certainty default must not be mutated."""
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p")
        assert p.certainty != "XXconfirmedXX"

    def test_evil_evidence_empty(self) -> None:
        """Evil: evidence default must be empty list."""
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p")
        assert p.evidence == []

    def test_evil_properties_empty(self) -> None:
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p")
        assert p.properties == {}

    def test_sad_override(self) -> None:
        p = EntityCreateParams(
            name="X",
            node_type="E",
            project_id="p",
            certainty="speculative",
            evidence=["ev1"],
        )
        assert p.certainty == "speculative"
        assert p.evidence == ["ev1"]

    def test_happy(self) -> None:
        """Happy: all defaults correct."""
        p = EntityCreateParams(name="X", node_type="Entity", project_id="p")
        assert p.certainty == "confirmed"
        assert p.evidence == []
        assert p.properties == {}


class TestEntityCommitReceiptDefaults:
    """Assert EntityCommitReceipt default values."""

    def test_evil_status(self) -> None:
        """Evil: status default must be 'committed'."""
        r = EntityCommitReceipt(id="1", name="X", operation_time_ms=0.0, total_memory_count=1)
        assert r.status == "committed"

    def test_evil_message(self) -> None:
        """Evil: message must contain 'committed'."""
        r = EntityCommitReceipt(id="1", name="X", operation_time_ms=0.0, total_memory_count=1)
        assert "committed" in r.message.lower()

    def test_evil_warnings_empty(self) -> None:
        """Evil: warnings default must be empty list."""
        r = EntityCommitReceipt(id="1", name="X", operation_time_ms=0.0, total_memory_count=1)
        assert r.warnings == []

    def test_sad_override(self) -> None:
        """Sad: custom message overrides default."""
        r = EntityCommitReceipt(
            id="1",
            name="X",
            operation_time_ms=0.0,
            total_memory_count=1,
            message="Custom",
        )
        assert r.message == "Custom"

    def test_happy(self) -> None:
        """Happy: all defaults correct."""
        r = EntityCommitReceipt(id="1", name="X", operation_time_ms=0.0, total_memory_count=1)
        assert r.status == "committed"
        assert r.message == "Memory committed to graph."
        assert r.warnings == []


class TestRelationshipDefaults:
    def test_evil_confidence(self) -> None:
        p = RelationshipCreateParams(from_entity="a", to_entity="b", relationship_type="DEPENDS_ON")
        assert p.confidence == 1.0

    def test_evil_weight(self) -> None:
        p = RelationshipCreateParams(from_entity="a", to_entity="b", relationship_type="DEPENDS_ON")
        assert p.weight == 1.0

    def test_evil_properties_empty(self) -> None:
        p = RelationshipCreateParams(from_entity="a", to_entity="b", relationship_type="DEPENDS_ON")
        assert p.properties == {}

    def test_sad_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            RelationshipCreateParams(from_entity="a", to_entity="b", relationship_type="INVALID")

    def test_happy(self) -> None:
        p = RelationshipCreateParams(from_entity="a", to_entity="b", relationship_type="ENABLES")
        assert p.confidence == 1.0
        assert p.weight == 1.0
        assert p.properties == {}


class TestBaseNodeDefaults:
    def test_evil_salience(self) -> None:
        n = BaseNode(name="X", node_type="Entity", project_id="p")
        assert n.salience_score == 1.0

    def test_evil_retrieval_count(self) -> None:
        n = BaseNode(name="X", node_type="Entity", project_id="p")
        assert n.retrieval_count == 0

    def test_evil_certainty(self) -> None:
        n = BaseNode(name="X", node_type="Entity", project_id="p")
        assert n.certainty == "confirmed"

    def test_sad_id_optional(self) -> None:
        n = BaseNode(name="X", node_type="Entity", project_id="p")
        assert n.id is None

    def test_happy(self) -> None:
        n = BaseNode(name="X", node_type="Entity", project_id="p")
        assert n.salience_score == 1.0
        assert n.retrieval_count == 0
        assert n.certainty == "confirmed"
        assert n.evidence == []
        assert n.embedding is None


class TestSearchResultDefaults:
    def test_evil_salience(self) -> None:
        r = SearchResult(id="1", name="X", node_type="E", project_id="p", score=0.9, distance=0.1)
        assert r.salience_score == 0.0

    def test_evil_observations(self) -> None:
        r = SearchResult(id="1", name="X", node_type="E", project_id="p", score=0.9, distance=0.1)
        assert r.observations == []

    def test_evil_relationships(self) -> None:
        r = SearchResult(id="1", name="X", node_type="E", project_id="p", score=0.9, distance=0.1)
        assert r.relationships == []

    def test_sad_content_optional(self) -> None:
        r = SearchResult(id="1", name="X", node_type="E", project_id="p", score=0.9, distance=0.1)
        assert r.content is None

    def test_happy(self) -> None:
        r = SearchResult(id="1", name="X", node_type="E", project_id="p", score=0.9, distance=0.1)
        assert r.salience_score == 0.0
        assert r.observations == []
        assert r.relationships == []


class TestEntityDeleteDefaults:
    def test_evil_soft_delete_true(self) -> None:
        p = EntityDeleteParams(entity_id="1", reason="test")
        assert p.soft_delete is True

    def test_evil_is_bool(self) -> None:
        p = EntityDeleteParams(entity_id="1", reason="test")
        assert isinstance(p.soft_delete, bool)

    def test_evil_override(self) -> None:
        p = EntityDeleteParams(entity_id="1", reason="test", soft_delete=False)
        assert p.soft_delete is False

    def test_sad_empty_reason(self) -> None:
        p = EntityDeleteParams(entity_id="1", reason="")
        assert p.reason == ""

    def test_happy(self) -> None:
        p = EntityDeleteParams(entity_id="1", reason="cleanup")
        assert p.soft_delete is True


class TestTemporalQueryDefaults:
    def test_evil_limit(self) -> None:
        p = TemporalQueryParams(start=datetime.now(UTC), end=datetime.now(UTC))
        assert p.limit == 20

    def test_evil_project_optional(self) -> None:
        p = TemporalQueryParams(start=datetime.now(UTC), end=datetime.now(UTC))
        assert p.project_id is None

    def test_evil_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TemporalQueryParams(start=datetime.now(UTC), end=datetime.now(UTC), limit=0)
        with pytest.raises(ValidationError):
            TemporalQueryParams(start=datetime.now(UTC), end=datetime.now(UTC), limit=101)

    def test_sad_boundary(self) -> None:
        p1 = TemporalQueryParams(start=datetime.now(UTC), end=datetime.now(UTC), limit=1)
        assert p1.limit == 1

    def test_happy(self) -> None:
        p = TemporalQueryParams(start=datetime.now(UTC), end=datetime.now(UTC))
        assert p.limit == 20
        assert p.project_id is None


class TestBottleQueryDefaults:
    def test_evil_limit(self) -> None:
        assert BottleQueryParams().limit == 10

    def test_evil_include_content(self) -> None:
        assert BottleQueryParams().include_content is False

    def test_evil_optional_none(self) -> None:
        p = BottleQueryParams()
        assert p.search_text is None
        assert p.before_date is None
        assert p.after_date is None
        assert p.project_id is None

    def test_sad_all_none(self) -> None:
        p = BottleQueryParams()
        fields = ("search_text", "before_date", "after_date", "project_id")
        assert all(getattr(p, f) is None for f in fields)

    def test_happy(self) -> None:
        p = BottleQueryParams()
        assert p.limit == 10
        assert p.include_content is False


class TestGapDetectionDefaults:
    def test_evil_min_similarity(self) -> None:
        assert GapDetectionParams().min_similarity == 0.7

    def test_evil_max_edges(self) -> None:
        p = GapDetectionParams()
        assert p.max_edges == 2
        assert p.max_edges != 3

    def test_evil_limit(self) -> None:
        assert GapDetectionParams().limit == 10

    def test_sad_zero_ok(self) -> None:
        assert GapDetectionParams(max_edges=0).max_edges == 0

    def test_happy(self) -> None:
        p = GapDetectionParams()
        assert p.min_similarity == 0.7
        assert p.max_edges == 2
        assert p.limit == 10


class TestObservationDefaults:
    def test_evil_certainty(self) -> None:
        assert ObservationParams(entity_id="1", content="t").certainty == "confirmed"

    def test_evil_evidence(self) -> None:
        assert ObservationParams(entity_id="1", content="t").evidence == []

    def test_evil_evidence_is_list(self) -> None:
        assert isinstance(ObservationParams(entity_id="1", content="t").evidence, list)

    def test_sad_override(self) -> None:
        p = ObservationParams(entity_id="1", content="t", certainty="speculative")
        assert p.certainty == "speculative"

    def test_happy(self) -> None:
        p = ObservationParams(entity_id="1", content="t")
        assert p.certainty == "confirmed"
        assert p.evidence == []


class TestSessionEndDefaults:
    def test_evil_outcomes_empty(self) -> None:
        assert SessionEndParams(session_id="s1", summary="d").outcomes == []

    def test_evil_outcomes_is_list(self) -> None:
        assert isinstance(SessionEndParams(session_id="s1", summary="d").outcomes, list)

    def test_evil_outcomes_len_zero(self) -> None:
        assert len(SessionEndParams(session_id="s1", summary="d").outcomes) == 0

    def test_sad_empty_summary(self) -> None:
        assert SessionEndParams(session_id="s1", summary="").summary == ""

    def test_happy(self) -> None:
        assert SessionEndParams(session_id="s1", summary="d").outcomes == []


class TestBreakthroughDefaults:
    def test_evil_analogy_none(self) -> None:
        assert BreakthroughParams(name="X", moment="Y", session_id="s1").analogy_used is None

    def test_evil_concepts_empty(self) -> None:
        assert BreakthroughParams(name="X", moment="Y", session_id="s1").concepts_unlocked == []

    def test_evil_concepts_is_list(self) -> None:
        bp = BreakthroughParams(name="X", moment="Y", session_id="s1")
        assert isinstance(bp.concepts_unlocked, list)

    def test_sad_empty_moment(self) -> None:
        assert BreakthroughParams(name="X", moment="", session_id="s1").moment == ""

    def test_happy(self) -> None:
        p = BreakthroughParams(name="X", moment="Y", session_id="s1")
        assert p.analogy_used is None
        assert p.concepts_unlocked == []


class TestEntityUpdateDefaults:
    def test_evil_reason_none(self) -> None:
        assert EntityUpdateParams(entity_id="1", properties={"k": "v"}).reason is None

    def test_evil_reason_not_empty_string(self) -> None:
        p = EntityUpdateParams(entity_id="1", properties={"k": "v"})
        assert p.reason is None
        assert p.reason != ""

    def test_evil_properties_preserved(self) -> None:
        props = {"key": "value", "num": 42}
        assert EntityUpdateParams(entity_id="1", properties=props).properties == props

    def test_sad_empty_properties(self) -> None:
        assert EntityUpdateParams(entity_id="1", properties={}).properties == {}

    def test_happy(self) -> None:
        p = EntityUpdateParams(entity_id="1", properties={"k": "v"}, reason="fix")
        assert p.entity_id == "1"
        assert p.properties == {"k": "v"}
        assert p.reason == "fix"
