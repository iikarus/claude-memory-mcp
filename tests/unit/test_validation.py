import pytest
from pydantic import ValidationError

from claude_memory.schema import EntityCreateParams, ObservationParams, RelationshipCreateParams


def test_entity_creation_validation() -> None:
    # Valid
    params = EntityCreateParams(
        name="Test", node_type="Entity", project_id="p1"  # Valid str for Literal
    )
    assert params.node_type == "Entity"

    # Invalid Node Type -> NOW VALID in Model (Runtime check only in Service)
    p2 = EntityCreateParams(name="Test", node_type="InvalidType", project_id="p1")
    assert p2.node_type == "InvalidType"


def test_relationship_validation() -> None:
    # Valid
    params = RelationshipCreateParams(
        from_entity="e1", to_entity="e2", relationship_type="DEPENDS_ON"
    )
    assert params.relationship_type == "DEPENDS_ON"

    # Invalid Edge Type
    with pytest.raises(ValidationError):
        RelationshipCreateParams(from_entity="e1", to_entity="e2", relationship_type="BAD_RELATION")


def test_observation_validation() -> None:
    # Valid
    params = ObservationParams(entity_id="e1", content="Observed something", certainty="confirmed")
    assert params.certainty == "confirmed"

    # Invalid Certainty
    with pytest.raises(ValidationError):
        ObservationParams(
            entity_id="e1",
            content="Observed something",
            certainty="maybe",  # valid: confirmed, likely, possible, unlikely
        )

    # Check valid values
    valid_certainties = ["confirmed", "speculative", "spitballing", "rejected"]
    for c in valid_certainties:
        ObservationParams(entity_id="e1", content="ok", certainty=c)
