"""MCP server exposing Exocortex memory tools via stdio transport."""

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from claude_memory.clustering import ClusteringService
from claude_memory.embedding import EmbeddingService
from claude_memory.librarian import LibrarianAgent
from claude_memory.schema import (
    BreakthroughParams,
    CertaintyLevel,
    EdgeType,
    EntityCommitReceipt,
    EntityCreateParams,
    EntityDeleteParams,
    EntityUpdateParams,
    ObservationParams,
    RelationshipCreateParams,
    RelationshipDeleteParams,
    SessionEndParams,
    SessionStartParams,
)
from claude_memory.tools import MemoryService

# Initialize MCP Server
mcp = FastMCP("claude-memory")

# Initialize Service
# Wire up dependencies explicitly
embedder = EmbeddingService()
service = MemoryService(embedding_service=embedder)
clustering = ClusteringService()
librarian = LibrarianAgent(service, clustering)


@mcp.tool()
async def create_entity(  # noqa: PLR0913
    name: str,
    node_type: str,
    project_id: str,
    properties: dict[str, Any] | None = None,
    certainty: CertaintyLevel = "confirmed",
    evidence: list[str] | None = None,
) -> EntityCommitReceipt:
    """Create a new entity in the memory graph."""
    if evidence is None:
        evidence = []
    if properties is None:
        properties = {}
    params = EntityCreateParams(
        name=name,
        node_type=node_type,
        project_id=project_id,
        properties=properties,
        certainty=certainty,
        evidence=evidence,
    )
    return await service.create_entity(params)


@mcp.tool()
async def update_entity(
    entity_id: str,
    properties: dict[str, Any],
    reason: str | None = None,
) -> dict[str, Any]:
    """Updates properties of an existing entity."""
    params = EntityUpdateParams(
        entity_id=entity_id,
        properties=properties,
        reason=reason,
    )
    return await service.update_entity(params)


@mcp.tool()
async def delete_entity(
    entity_id: str,
    reason: str,
    soft_delete: bool = True,
) -> dict[str, Any]:
    """Deletes (or soft deletes) an entity."""
    params = EntityDeleteParams(
        entity_id=entity_id,
        reason=reason,
        soft_delete=soft_delete,
    )
    return await service.delete_entity(params)


@mcp.tool()
async def create_relationship(  # noqa: PLR0913
    from_entity: str,
    to_entity: str,
    relationship_type: EdgeType,
    properties: dict[str, Any] | None = None,
    confidence: float = 1.0,
    weight: float = 1.0,
) -> dict[str, Any]:
    """Create a relationship between two entities. Weight (0-1) indicates strength."""
    if properties is None:
        properties = {}
    params = RelationshipCreateParams(
        from_entity=from_entity,
        to_entity=to_entity,
        relationship_type=relationship_type,
        properties=properties,
        confidence=confidence,
        weight=weight,
    )
    return await service.create_relationship(params)


@mcp.tool()
async def delete_relationship(
    relationship_id: str,
    reason: str,
) -> dict[str, Any]:
    """Deletes a relationship."""
    params = RelationshipDeleteParams(
        relationship_id=relationship_id,
        reason=reason,
    )
    return await service.delete_relationship(params)


@mcp.tool()
async def add_observation(
    entity_id: str,
    content: str,
    certainty: CertaintyLevel = "confirmed",
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Adds an observation node linked to an entity."""
    if evidence is None:
        evidence = []
    params = ObservationParams(
        entity_id=entity_id,
        content=content,
        certainty=certainty,
        evidence=evidence,
    )
    return await service.add_observation(params)


@mcp.tool()
async def start_session(project_id: str, focus: str) -> dict[str, Any]:
    """Starts a new session context."""
    params = SessionStartParams(project_id=project_id, focus=focus)
    return await service.start_session(params)


@mcp.tool()
async def end_session(
    session_id: str, summary: str, outcomes: list[str] | None = None
) -> dict[str, Any]:
    """Ends a session and records summary."""
    if outcomes is None:
        outcomes = []
    params = SessionEndParams(session_id=session_id, summary=summary, outcomes=outcomes)
    return await service.end_session(params)


@mcp.tool()
async def record_breakthrough(
    name: str,
    moment: str,
    session_id: str,
    analogy_used: str | None = None,
    concepts_unlocked: list[str] | None = None,
) -> dict[str, Any]:
    """Record a learning breakthrough."""
    if concepts_unlocked is None:
        concepts_unlocked = []
    params = BreakthroughParams(
        name=name,
        moment=moment,
        session_id=session_id,
        analogy_used=analogy_used,
        concepts_unlocked=concepts_unlocked,
    )
    return await service.record_breakthrough(params)


@mcp.tool()
async def get_neighbors(
    entity_id: str, depth: int = 1, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Retrieve neighboring entities up to a certain depth."""
    return await service.get_neighbors(entity_id, depth, limit, offset)


@mcp.tool()
async def traverse_path(from_id: str, to_id: str) -> list[dict[str, Any]]:
    """Find the shortest path between two entities."""
    return await service.traverse_path(from_id, to_id)


@mcp.tool()
async def find_cross_domain_patterns(entity_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Analyzes the graph for non-obvious connections between disparate domains."""
    return await service.find_cross_domain_patterns(entity_id, limit)


@mcp.tool()
async def get_evolution(entity_id: str) -> list[dict[str, Any]]:
    """Retrieve the evolution (history/observations) of an entity."""
    return await service.get_evolution(entity_id)


@mcp.tool()
async def point_in_time_query(query_text: str, as_of: str) -> list[dict[str, Any]]:
    """Execute a search considering only knowledge known before `as_of`."""
    return await service.point_in_time_query(query_text, as_of)


@mcp.tool()
async def archive_entity(entity_id: str) -> dict[str, Any]:
    """Archive an entity (logical hide."""
    return await service.archive_entity(entity_id)


@mcp.tool()
async def prune_stale(days: int = 30) -> dict[str, Any]:
    """Hard delete archived entities older than N days."""
    return await service.prune_stale(days)


@mcp.tool()
async def search_memory(
    query: str, project_id: str | None = None, limit: int = 10, offset: int = 0
) -> list[dict[str, Any]] | str:
    """Search for entities using hybrid search. Use offset for pagination."""
    results = await service.search(query, limit, project_id, offset)
    if not results:
        return "No results found."
    return [res.model_dump() for res in results]


@mcp.tool()
async def run_librarian_cycle() -> dict[str, Any]:
    """Triggers the Librarian Agent to cluster and consolidate memories."""
    return await librarian.run_cycle()


@mcp.tool()
async def create_memory_type(
    name: str, description: str, required_properties: list[str] | None = None
) -> dict[str, Any]:
    """Registers a new memory type in the ontology.

    Args:
        name: Name of the new type (e.g. "Recipe")
        description: Description of what this type represents
        required_properties: List of property names that should always be present
    """
    if required_properties is None:
        required_properties = []
    return service.create_memory_type(name, description, required_properties)


def main() -> None:
    """Launch the MCP server via stdio transport."""
    from claude_memory.logging_config import configure_logging  # noqa: PLC0415

    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
