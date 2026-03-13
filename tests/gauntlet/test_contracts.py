"""MCP Tool Contracts & Snapshots — Gauntlet R8.

Tests Pydantic schema contracts and response shape snapshots:
- R8A: Input validation contracts for EntityCreateParams, RelationshipCreateParams, etc.
- R8B: Output shape snapshots for EntityCommitReceipt, SearchResult, etc.
- R8C: deal-style post-conditions on schema construction

No Docker required — tests pure Pydantic validation logic.
"""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from claude_memory.schema import (
    BottleQueryParams,
    BreakthroughParams,
    EntityCommitReceipt,
    EntityCreateParams,
    EntityDeleteParams,
    GapDetectionParams,
    ObservationParams,
    RelationshipCreateParams,
    RelationshipDeleteParams,
    SearchResult,
    SessionEndParams,
    SessionStartParams,
    TemporalQueryParams,
)

# ═══════════════════════════════════════════════════════════════
#  R8A: Input Validation Contracts
# ═══════════════════════════════════════════════════════════════


class TestEntityCreateContract:
    """Contract: EntityCreateParams accepts valid input, rejects bad input."""

    def test_valid_input_returns_params(self):
        """C1: Valid input → constructs successfully with all fields."""
        params = EntityCreateParams(name="Entropy", node_type="Concept", project_id="physics")
        assert params.name == "Entropy"
        assert params.node_type == "Concept"
        assert params.project_id == "physics"
        assert params.certainty == "confirmed"  # default
        assert params.evidence == []  # default
        assert params.properties == {}  # default

    def test_missing_required_name_raises(self):
        """C2: Missing name → ValidationError."""
        with pytest.raises(ValidationError):
            EntityCreateParams(node_type="Concept", project_id="physics")

    def test_missing_required_node_type_raises(self):
        """C3: Missing node_type → ValidationError."""
        with pytest.raises(ValidationError):
            EntityCreateParams(name="Entropy", project_id="physics")

    def test_missing_required_project_id_raises(self):
        """C4: Missing project_id → ValidationError."""
        with pytest.raises(ValidationError):
            EntityCreateParams(name="Entropy", node_type="Concept")

    def test_invalid_certainty_raises(self):
        """C5: Invalid certainty level → ValidationError."""
        with pytest.raises(ValidationError):
            EntityCreateParams(
                name="Entropy",
                node_type="Concept",
                project_id="physics",
                certainty="INVALID_LEVEL",
            )


class TestRelationshipCreateContract:
    """Contract: RelationshipCreateParams validates edge types and weights."""

    def test_valid_edge_type_accepted(self):
        """C6: Valid EdgeType → accepted."""
        params = RelationshipCreateParams(
            from_entity="a", to_entity="b", relationship_type="DEPENDS_ON"
        )
        assert params.relationship_type == "DEPENDS_ON"

    def test_invalid_edge_type_rejected(self):
        """C7: Invalid EdgeType → ValidationError."""
        with pytest.raises(ValidationError):
            RelationshipCreateParams(
                from_entity="a", to_entity="b", relationship_type="INVALID_TYPE"
            )

    def test_weight_default_is_one(self):
        """C8: Default weight = 1.0."""
        params = RelationshipCreateParams(
            from_entity="a", to_entity="b", relationship_type="RELATED_TO"
        )
        assert params.weight == 1.0

    def test_weight_negative_rejected(self):
        """C9: Negative weight → ValidationError."""
        with pytest.raises(ValidationError):
            RelationshipCreateParams(
                from_entity="a",
                to_entity="b",
                relationship_type="RELATED_TO",
                weight=-0.1,
            )

    def test_weight_above_one_rejected(self):
        """C10: Weight > 1.0 → ValidationError."""
        with pytest.raises(ValidationError):
            RelationshipCreateParams(
                from_entity="a",
                to_entity="b",
                relationship_type="RELATED_TO",
                weight=1.5,
            )


class TestObservationContract:
    """Contract: ObservationParams validates required fields."""

    def test_valid_observation(self):
        """C11: Valid observation params."""
        params = ObservationParams(entity_id="abc", content="some observation")
        assert params.content == "some observation"

    def test_missing_content_raises(self):
        """C12: Missing content → ValidationError."""
        with pytest.raises(ValidationError):
            ObservationParams(entity_id="abc")

    def test_missing_entity_id_raises(self):
        """C13: Missing entity_id → ValidationError."""
        with pytest.raises(ValidationError):
            ObservationParams(content="some observation")


class TestSessionContract:
    """Contract: Session params validate required fields."""

    def test_start_session_valid(self):
        """C14: Valid session start."""
        params = SessionStartParams(project_id="test", focus="testing")
        assert params.project_id == "test"

    def test_end_session_valid(self):
        """C15: Valid session end."""
        params = SessionEndParams(session_id="s1", summary="done")
        assert params.outcomes == []  # default

    def test_end_session_with_outcomes(self):
        """C16: Session end with outcomes."""
        params = SessionEndParams(session_id="s1", summary="done", outcomes=["learned X"])
        assert params.outcomes == ["learned X"]


class TestDeleteContract:
    """Contract: Delete params validate required fields."""

    def test_entity_delete_valid(self):
        """C17: Valid entity delete."""
        params = EntityDeleteParams(entity_id="abc", reason="obsolete")
        assert params.soft_delete is True  # default

    def test_relationship_delete_valid(self):
        """C18: Valid relationship delete."""
        params = RelationshipDeleteParams(relationship_id="rel1", reason="wrong")
        assert params.relationship_id == "rel1"


class TestBreakthroughContract:
    """Contract: BreakthroughParams validates required fields."""

    def test_valid_breakthrough(self):
        """C19: Valid breakthrough."""
        params = BreakthroughParams(name="Eureka", moment="Just now", session_id="s1")
        assert params.concepts_unlocked == []

    def test_missing_session_raises(self):
        """C20: Missing session_id → ValidationError."""
        with pytest.raises(ValidationError):
            BreakthroughParams(name="Eureka", moment="Just now")


# ═══════════════════════════════════════════════════════════════
#  R8B: Output Shape Snapshots
# ═══════════════════════════════════════════════════════════════


class TestOutputShapeSnapshots:
    """Snapshot tests — verify output schemas have expected field sets."""

    def test_entity_commit_receipt_shape(self):
        """S1: EntityCommitReceipt has expected fields."""
        receipt = EntityCommitReceipt(
            id="abc-123",
            name="Test",
            operation_time_ms=42.5,
            total_memory_count=100,
        )
        data = receipt.model_dump()
        assert set(data.keys()) == {
            "id",
            "name",
            "status",
            "operation_time_ms",
            "total_memory_count",
            "message",
            "warnings",
        }
        assert data["status"] == "committed"
        assert data["warnings"] == []

    def test_search_result_shape(self):
        """S2: SearchResult has expected fields."""
        result = SearchResult(
            id="id-1",
            name="Entropy",
            node_type="Concept",
            project_id="physics",
            score=0.95,
            distance=0.05,
        )
        data = result.model_dump()
        expected_keys = {
            "id",
            "name",
            "node_type",
            "project_id",
            "content",
            "score",
            "distance",
            "salience_score",
            "observations",
            "relationships",
            # ADR-007 hybrid search fields
            "retrieval_strategy",
            "recency_score",
            "path_distance",
            "activation_score",
            "vector_score",
        }
        assert set(data.keys()) == expected_keys

    def test_search_result_defaults(self):
        """S3: SearchResult defaults are correct."""
        result = SearchResult(
            id="id-1",
            name="Test",
            node_type="Concept",
            project_id="test",
            score=0.9,
            distance=0.1,
        )
        assert result.content is None
        assert result.salience_score == 0.0
        assert result.observations == []
        assert result.relationships == []

    def test_gap_detection_params_shape(self):
        """S4: GapDetectionParams has expected defaults."""
        params = GapDetectionParams()
        data = params.model_dump()
        assert data["min_similarity"] == 0.7
        assert data["max_edges"] == 2
        assert data["limit"] == 10

    def test_bottle_query_params_shape(self):
        """S5: BottleQueryParams has expected defaults."""
        params = BottleQueryParams()
        data = params.model_dump()
        assert data["limit"] == 10
        assert data["include_content"] is False
        assert data["search_text"] is None
        assert data["before_date"] is None
        assert data["after_date"] is None
        assert data["project_id"] is None

    def test_temporal_query_params_shape(self):
        """S6: TemporalQueryParams serializes dates correctly."""
        params = TemporalQueryParams(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 2, 1, tzinfo=UTC),
        )
        data = json.loads(params.model_dump_json())
        assert "start" in data
        assert "end" in data
        assert data["limit"] == 20  # default


# ═══════════════════════════════════════════════════════════════
#  R8C: Round-Trip Contract Verification
# ═══════════════════════════════════════════════════════════════


class TestRoundTripContracts:
    """Verify serialize → deserialize round-trips preserve data."""

    def test_entity_create_roundtrip(self):
        """RT1: EntityCreateParams survives JSON round-trip."""
        original = EntityCreateParams(
            name="Entropy",
            node_type="Concept",
            project_id="physics",
            properties={"key": "value"},
            certainty="speculative",
            evidence=["paper.pdf"],
        )
        restored = EntityCreateParams.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_relationship_create_roundtrip(self):
        """RT2: RelationshipCreateParams survives JSON round-trip."""
        original = RelationshipCreateParams(
            from_entity="a",
            to_entity="b",
            relationship_type="DEPENDS_ON",
            weight=0.7,
        )
        restored = RelationshipCreateParams.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_search_result_roundtrip(self):
        """RT3: SearchResult survives JSON round-trip."""
        original = SearchResult(
            id="id-1",
            name="Test",
            node_type="Concept",
            project_id="test",
            score=0.95,
            distance=0.05,
            observations=["obs1", "obs2"],
            relationships=[{"src": "a", "dst": "b"}],
        )
        restored = SearchResult.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_commit_receipt_roundtrip(self):
        """RT4: EntityCommitReceipt survives JSON round-trip."""
        original = EntityCommitReceipt(
            id="abc",
            name="Test",
            operation_time_ms=42.5,
            total_memory_count=100,
            warnings=["w1"],
        )
        restored = EntityCommitReceipt.model_validate_json(original.model_dump_json())
        assert restored == original
