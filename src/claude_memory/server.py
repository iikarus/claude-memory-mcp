"""MCP server exposing Claude Memory tools via stdio transport."""

import logging
from typing import Any, Literal

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
from claude_memory.tools_extra import (
    configure as _configure_extra_tools,
)
from claude_memory.tools_extra import (
    create_memory_type,  # noqa: F401 — re-export for backward compat
    find_knowledge_gaps,  # noqa: F401
    get_bottles,  # noqa: F401
    get_temporal_neighbors,  # noqa: F401
    graph_health,  # noqa: F401
    query_timeline,  # noqa: F401
    run_librarian_cycle,  # noqa: F401
    search_associative,  # noqa: F401
)

# Initialize MCP Server
mcp = FastMCP("claude-memory")

# Initialize Service
# Wire up dependencies explicitly
embedder = EmbeddingService()
service = MemoryService(embedding_service=embedder)
clustering = ClusteringService()
librarian = LibrarianAgent(service, clustering)

# Register extra tool handlers (temporal, search variants, health, librarian)
_configure_extra_tools(mcp, service, librarian)


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
async def search_memory(  # noqa: PLR0913
    query: str,
    project_id: str | None = None,
    limit: int = 10,
    offset: int = 0,
    mmr: bool = False,
    strategy: str | None = None,
    temporal_window_days: int = 7,
    include_meta: bool = False,
) -> list[dict[str, Any]] | dict[str, Any] | str:
    """Search for entities. mmr=True for diverse results.

    strategy: 'semantic', 'associative', 'temporal', 'relational', or None (hybrid default).
    temporal_window_days: lookback window for temporal queries (default 7).
    include_meta: when True, wraps results with temporal exhaustion metadata.
    """
    results = await service.search(
        query,
        limit,
        project_id,
        offset,
        mmr=mmr,
        strategy=strategy,
        temporal_window_days=temporal_window_days,
    )
    if not results:
        return "No results found."

    result_dicts = [res.model_dump() for res in results]

    # Return temporal metadata envelope when opted-in
    if include_meta and hasattr(service, "_last_detected_intent"):
        from claude_memory.router import QueryIntent  # noqa: PLC0415
        from claude_memory.schema import HybridSearchResponse  # noqa: PLC0415

        if service._last_detected_intent == QueryIntent.TEMPORAL:
            response = HybridSearchResponse(
                results=results,
                meta={
                    "temporal_exhausted": getattr(service, "_last_temporal_exhausted", False),
                    "temporal_window_days": getattr(service, "_last_temporal_window_days", 7),
                    "temporal_result_count": getattr(service, "_last_temporal_result_count", 0),
                    "suggestion": (
                        "Widen temporal_window_days for more historical results"
                        if getattr(service, "_last_temporal_exhausted", False)
                        else None
                    ),
                },
            )
            return response.model_dump()

    return result_dicts


@mcp.tool()
async def analyze_graph(
    algorithm: Literal["pagerank", "louvain"] = "pagerank",
) -> list[dict[str, Any]]:
    """Runs graph algorithms (pagerank or louvain) to find key entities or communities."""
    return await service.analyze_graph(algorithm=algorithm)


@mcp.tool()
async def get_hologram(
    query: str,
    depth: int = 1,
    max_tokens: int = 8000,
) -> dict[str, Any]:
    """Retrieves a 'Hologram' — a connected subgraph relevant to the query."""
    return await service.get_hologram(query, depth=depth, max_tokens=max_tokens)


@mcp.tool()
async def search_stats() -> dict[str, Any]:
    """Return rolling-window search behaviour statistics (DRIFT-002).

    Reports distribution of retrieval strategies, score percentiles,
    vector score null rates, and latency — useful for detecting
    behavioural drift over time.
    """
    if service._stats is None:
        return {"status": "stats not enabled", "searches_recorded": 0}
    return service._stats.report()


_background_tasks: set[object] = set()  # prevent GC of fire-and-forget tasks


def main() -> None:
    """Launch the MCP server via stdio transport."""
    import asyncio  # noqa: PLC0415

    from claude_memory.logging_config import configure_logging  # noqa: PLC0415
    from claude_memory.update_check import check_for_updates  # noqa: PLC0415

    configure_logging()
    logger = logging.getLogger(__name__)

    # Fire-and-forget update check — never blocks startup
    try:
        loop = asyncio.get_event_loop()
        task = loop.create_task(check_for_updates())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        pass  # No event loop yet — server will create one

    logger.info("Starting MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
