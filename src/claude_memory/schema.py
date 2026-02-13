"""Pydantic schemas for memory entities, relationships, sessions, and search results."""

from datetime import UTC, datetime
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
    "CONCURRENT_WITH",
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    occurred_at: datetime | None = Field(
        default=None, description="When the event actually happened"
    )

    # Epistemic
    certainty: CertaintyLevel = "confirmed"
    evidence: list[str] = Field(default_factory=list)

    # Salience
    salience_score: float = Field(default=1.0, description="Retrieval-based salience")
    retrieval_count: int = Field(default=0, description="Total times retrieved via search")

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
    warnings: list[str] = Field(default_factory=list)


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


class TemporalQueryParams(BaseModel):
    """Parameters for querying entities within a time window."""

    start: datetime
    end: datetime
    limit: int = Field(default=20, ge=1, le=100)
    project_id: str | None = None


class SearchResult(BaseModel):
    """A single result from semantic search across the memory graph."""

    id: str
    name: str
    node_type: str
    project_id: str
    content: str | None = None  # For Observations
    score: float
    distance: float
    salience_score: float = Field(default=0.0, description="Entity salience at retrieval time")
    observations: list[str] = Field(default_factory=list, description="E-2: observation texts")
    relationships: list[dict[str, str]] = Field(
        default_factory=list, description="E-2: connected edges"
    )


class BottleQueryParams(BaseModel):
    """Parameters for querying 'Message in a Bottle' entities."""

    limit: int = Field(default=10, ge=1, le=100)
    search_text: str | None = None
    before_date: datetime | None = None
    after_date: datetime | None = None
    project_id: str | None = None
    include_content: bool = False


class GapDetectionParams(BaseModel):
    """Parameters for structural gap detection between knowledge clusters."""

    min_similarity: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum centroid similarity threshold"
    )
    max_edges: int = Field(
        default=2, ge=0, description="Maximum cross-cluster edges to qualify as a gap"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Max gaps to return")
