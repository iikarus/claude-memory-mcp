from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# === ENUMS ===

NodeLabel = Literal[
    "Person",
    "Project",
    "Concept",
    "Decision",
    "Session",
    "Breakthrough",
    "Analogy",
    "Observation",
    "Tool",
    "Issue",
    "Entity",  # Fallback
]

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
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    name: str
    node_type: NodeLabel
    project_id: str = Field(description="Namespace/Project ID")

    # Temporal
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Epistemic
    certainty: CertaintyLevel = "confirmed"
    evidence: List[str] = Field(default_factory=list)

    # Search
    embedding: Optional[List[float]] = None


class EntityCommitReceipt(BaseModel):
    id: str
    name: str
    status: Literal["committed"] = "committed"
    operation_time_ms: float
    total_memory_count: int
    message: str = "Memory committed to graph."


class BreakthroughParams(BaseModel):
    name: str
    moment: str
    session_id: str
    analogy_used: Optional[str] = None
    concepts_unlocked: List[str] = Field(default_factory=list)


class EntityCreateParams(BaseModel):
    name: str
    node_type: NodeLabel
    project_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    certainty: CertaintyLevel = "confirmed"
    evidence: List[str] = Field(default_factory=list)


class RelationshipCreateParams(BaseModel):
    from_entity: str
    to_entity: str
    relationship_type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class EntityUpdateParams(BaseModel):
    entity_id: str
    properties: Dict[str, Any]
    reason: Optional[str] = None


class EntityDeleteParams(BaseModel):
    entity_id: str
    reason: str
    soft_delete: bool = True


class RelationshipDeleteParams(BaseModel):
    relationship_id: str
    reason: str


class ObservationParams(BaseModel):
    entity_id: str
    content: str
    certainty: CertaintyLevel = "confirmed"
    evidence: List[str] = Field(default_factory=list)


class SessionStartParams(BaseModel):
    project_id: str
    focus: str


class SessionEndParams(BaseModel):
    session_id: str
    summary: str
    outcomes: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    id: str
    name: str
    node_type: str
    project_id: str
    content: Optional[str] = None  # For Observations
    score: float
    distance: float
