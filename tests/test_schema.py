from claude_memory.schema import BreakthroughParams, EntityCreateParams, RelationshipCreateParams


def test_entity_creation_valid() -> None:
    """Test creating a valid entity params object."""
    params = EntityCreateParams(
        name="Test Entity",
        node_type="Concept",
        project_id="test_project",
        properties={"description": "A test concept"},
    )
    assert params.name == "Test Entity"
    assert params.node_type == "Concept"
    assert params.certainty == "confirmed"  # default


def test_entity_creation_invalid_type() -> None:
    """Test that invalid node types are accepted by the model (runtime validation handles it)."""
    # Pydantic allows any string now.
    params = EntityCreateParams(
        name="Bad Entity", node_type="InvalidType", project_id="test_project", properties={}
    )
    assert params.node_type == "InvalidType"


def test_relationship_creation() -> None:
    """Test relationship params."""
    params = RelationshipCreateParams(
        from_entity="uuid1", to_entity="uuid2", relationship_type="DEPENDS_ON", confidence=0.8
    )
    assert params.relationship_type == "DEPENDS_ON"
    assert params.confidence == 0.8


def test_breakthrough_params() -> None:
    """Test breakthrough params."""
    params = BreakthroughParams(
        name="Eureka",
        moment="Found the bug",
        session_id="session-123",
        analogy_used="Needle in haystack",
    )
    assert params.name == "Eureka"
    assert params.analogy_used == "Needle in haystack"
