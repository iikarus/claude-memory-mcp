from typing import Any, Dict, List, Optional, Union, cast

from mcp.server.fastmcp import FastMCP

from claude_memory.clustering import ClusteringService
from claude_memory.embedding import EmbeddingService
from claude_memory.librarian import LibrarianAgent
from claude_memory.schema import (
    BreakthroughParams,
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


@mcp.tool()  # type: ignore[misc]
async def create_entity(
    name: str,
    node_type: str,
    project_id: str,
    properties: Dict[str, Any] = {},
    certainty: str = "confirmed",
    evidence: List[str] = [],
) -> EntityCommitReceipt:
    """Create a new entity in the memory graph."""
    params = EntityCreateParams(
        name=name,
        node_type=node_type,
        project_id=project_id,
        properties=properties,
        certainty=certainty,
        evidence=evidence,
    )
    return await service.create_entity(params)


@mcp.tool()  # type: ignore[misc]
async def update_entity(
    entity_id: str,
    properties: Dict[str, Any],
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates properties of an existing entity."""
    params = EntityUpdateParams(
        entity_id=entity_id,
        properties=properties,
        reason=reason,
    )
    return await service.update_entity(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def delete_entity(
    entity_id: str,
    reason: str,
    soft_delete: bool = True,
) -> Dict[str, Any]:
    """Deletes (or soft deletes) an entity."""
    params = EntityDeleteParams(
        entity_id=entity_id,
        reason=reason,
        soft_delete=soft_delete,
    )
    return await service.delete_entity(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def create_relationship(
    from_entity: str,
    to_entity: str,
    relationship_type: str,
    properties: Dict[str, Any] = {},
    confidence: float = 1.0,
) -> Dict[str, Any]:
    """Create a relationship between two entities."""
    params = RelationshipCreateParams(
        from_entity=from_entity,
        to_entity=to_entity,
        relationship_type=relationship_type,
        properties=properties,
        confidence=confidence,
    )
    return await service.create_relationship(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def delete_relationship(
    relationship_id: str,
    reason: str,
) -> Dict[str, Any]:
    """Deletes a relationship."""
    params = RelationshipDeleteParams(
        relationship_id=relationship_id,
        reason=reason,
    )
    return await service.delete_relationship(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def add_observation(
    entity_id: str,
    content: str,
    certainty: str = "confirmed",
    evidence: List[str] = [],
) -> Dict[str, Any]:
    """Adds an observation node linked to an entity."""
    params = ObservationParams(
        entity_id=entity_id,
        content=content,
        certainty=certainty,
        evidence=evidence,
    )
    return await service.add_observation(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def start_session(project_id: str, focus: str) -> Dict[str, Any]:
    """Starts a new session context."""
    params = SessionStartParams(project_id=project_id, focus=focus)
    return await service.start_session(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def end_session(session_id: str, summary: str, outcomes: List[str] = []) -> Dict[str, Any]:
    """Ends a session and records summary."""
    params = SessionEndParams(session_id=session_id, summary=summary, outcomes=outcomes)
    return await service.end_session(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def record_breakthrough(
    name: str,
    moment: str,
    session_id: str,
    analogy_used: Optional[str] = None,
    concepts_unlocked: List[str] = [],
) -> Dict[str, Any]:
    """Record a learning breakthrough."""
    params = BreakthroughParams(
        name=name,
        moment=moment,
        session_id=session_id,
        analogy_used=analogy_used,
        concepts_unlocked=concepts_unlocked,
    )
    return await service.record_breakthrough(params)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def get_neighbors(entity_id: str, depth: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve neighboring entities up to a certain depth."""
    return await service.get_neighbors(entity_id, depth, limit)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def traverse_path(from_id: str, to_id: str) -> List[Dict[str, Any]]:
    """Find the shortest path between two entities."""
    return await service.traverse_path(from_id, to_id)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def find_cross_domain_patterns(entity_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Analyzes the graph for non-obvious connections between disparate domains."""
    return await service.find_cross_domain_patterns(entity_id, limit)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def get_evolution(entity_id: str) -> List[Dict[str, Any]]:
    """Retrieve the evolution (history/observations) of an entity."""
    return await service.get_evolution(entity_id)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def point_in_time_query(query_text: str, as_of: str) -> List[Dict[str, Any]]:
    """Execute a search considering only knowledge known before `as_of`."""
    return await service.point_in_time_query(query_text, as_of)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def archive_entity(entity_id: str) -> Dict[str, Any]:
    """Archive an entity (logical hide."""
    return await service.archive_entity(entity_id)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def prune_stale(days: int = 30) -> Dict[str, Any]:
    """Hard delete archived entities older than N days."""
    return await service.prune_stale(days)  # type: ignore


@mcp.tool()  # type: ignore[misc]
async def search_memory(
    query: str, project_id: Optional[str] = None, limit: int = 10
) -> Union[List[Dict[str, Any]], str]:
    """Search for entities using hybrid search."""
    results = await service.search(query, project_id, limit)
    if not results:
        return "No results found."
    return [res.model_dump() for res in results]


@mcp.tool()  # type: ignore[misc]
async def run_librarian_cycle() -> Dict[str, Any]:
    """Triggers the Librarian Agent to cluster and consolidate memories."""
    return cast(Dict[str, Any], await librarian.run_cycle())


@mcp.tool()  # type: ignore[misc]
async def create_memory_type(
    name: str, description: str, required_properties: List[str] = []
) -> Dict[str, Any]:
    """Registers a new memory type in the ontology.

    Args:
        name: Name of the new type (e.g. "Recipe")
        description: Description of what this type represents
        required_properties: List of property names that should always be present
    """
    return cast(Dict[str, Any], service.create_memory_type(name, description, required_properties))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
