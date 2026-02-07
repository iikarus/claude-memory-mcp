"""Pydantic schemas for memory entities, relationships, sessions, and search results."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# === ENUMS ===

NodeLabel = str  # Dynamic: Validated by OntologyManager

EdgeType = Literal[
    # Structural
    "DEPENDS_ON",
    "ENABLES",
    "BLOCKS",
    "CONTAINS",
    "PART_OF",
    # Temporal
    "EVOLVED_FROM",
    "SUPERSEDES",
    "PRECEDED_BY",
    # Epistemic
    "CONTRADICTS",
    "SUPPORTS",
    "REJECTED_FOR",
    "REVISITED_BECAUSE",
    # Cross-Domain
    "RHYMES_WITH",
    "ANALOGOUS_TO",
    # Learning
    "TAUGHT_THROUGH",
    "BREAKTHROUGH_IN",
    "UNLOCKED",
    # Attribution
    "CREATED_BY",
    "DECIDED_IN",
    "MENTIONED_IN",
    # Project
    "BELONGS_TO_PROJECT",
    "BRIDGES_TO",
    "RELATED_TO",  # Fallback
]

CertaintyLevel = Literal["confirmed", "speculative", "spitballing", "rejected", "revisited"]

# === MODELS ===


class BaseNode(BaseModel):
    """Base schema for all memory graph nodes."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    node_type: NodeLabel
    project_id: str = Field(description="Namespace/Project ID")

    # Temporal
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Epistemic
    certainty: CertaintyLevel = "confirmed"
    evidence: list[str] = Field(default_factory=list)

    # Search
    embedding: list[float] | None = None


class EntityCommitReceipt(BaseModel):
    """Receipt returned after committing an entity to the graph."""

    id: str
    name: str
    status: Literal["committed"] = "committed"
    operation_time_ms: float
    total_memory_count: int
    message: str = "Memory committed to graph."


class BreakthroughParams(BaseModel):
    """Parameters for recording a learning breakthrough."""

    name: str
    moment: str
    session_id: str
    analogy_used: str | None = None
    concepts_unlocked: list[str] = Field(default_factory=list)


class EntityCreateParams(BaseModel):
    """Parameters for creating a new entity node."""

    name: str
    node_type: NodeLabel
    project_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    certainty: CertaintyLevel = "confirmed"
    evidence: list[str] = Field(default_factory=list)


class RelationshipCreateParams(BaseModel):
    """Parameters for creating a typed relationship between entities."""

    from_entity: str
    to_entity: str
    relationship_type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength 0-1")


class EntityUpdateParams(BaseModel):
    """Parameters for updating an existing entity's properties."""

    entity_id: str
    properties: dict[str, Any]
    reason: str | None = None


class EntityDeleteParams(BaseModel):
    """Parameters for deleting (or archiving) an entity."""

    entity_id: str
    reason: str
    soft_delete: bool = True


class RelationshipDeleteParams(BaseModel):
    """Parameters for deleting a relationship."""

    relationship_id: str
    reason: str


class ObservationParams(BaseModel):
    """Parameters for adding an observation to an entity."""

    entity_id: str
    content: str
    certainty: CertaintyLevel = "confirmed"
    evidence: list[str] = Field(default_factory=list)


class SessionStartParams(BaseModel):
    """Parameters for starting a new working session."""

    project_id: str
    focus: str


class SessionEndParams(BaseModel):
    """Parameters for ending and summarizing a session."""

    session_id: str
    summary: str
    outcomes: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """A single result from semantic search across the memory graph."""

    id: str
    name: str
    node_type: str
    project_id: str
    content: str | None = None  # For Observations
    score: float
    distance: float
