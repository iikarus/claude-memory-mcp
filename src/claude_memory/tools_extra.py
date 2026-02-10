"""Extra MCP tool handlers — search variants, temporal, librarian, health.

Functions are defined at module level so they can be imported by tests.
``configure()`` is called from ``server.py`` to bind the MCP app and
inject service references before any tool is invoked.
"""

from typing import Any

from claude_memory.schema import (
    BottleQueryParams,
    GapDetectionParams,
    TemporalQueryParams,
)

# Late-bound references, set by configure()
_service: Any = None
_librarian: Any = None


def configure(mcp, service, librarian) -> None:
    """Bind service dependencies and register handlers on the MCP app.

    Must be called once from ``server.py`` before any tool is invoked.
    """
    global _service, _librarian  # noqa: PLW0603
    _service = service
    _librarian = librarian

    mcp.tool()(search_associative)
    mcp.tool()(run_librarian_cycle)
    mcp.tool()(create_memory_type)
    mcp.tool()(query_timeline)
    mcp.tool()(get_temporal_neighbors)
    mcp.tool()(get_bottles)
    mcp.tool()(graph_health)
    mcp.tool()(find_knowledge_gaps)


async def search_associative(  # noqa: PLR0913
    query: str,
    limit: int = 10,
    project_id: str | None = None,
    decay: float = 0.6,
    max_hops: int = 3,
    w_sim: float | None = None,
    w_act: float | None = None,
    w_sal: float | None = None,
    w_rec: float | None = None,
) -> list[dict[str, Any]]:
    """Associative search using spreading activation through the knowledge graph.

    Combines vector similarity with graph-based energy propagation for
    richer, context-aware retrieval.  Score weights default to env vars
    ``W_SIMILARITY``, ``W_ACTIVATION``, ``W_SALIENCE``, ``W_RECENCY``.
    """
    results = await _service.search_associative(
        query,
        limit=limit,
        project_id=project_id,
        decay=decay,
        max_hops=max_hops,
        w_sim=w_sim,
        w_act=w_act,
        w_sal=w_sal,
        w_rec=w_rec,
    )
    if not results:
        return [{"message": "No results found."}]
    return [res.model_dump() for res in results]


async def run_librarian_cycle() -> dict[str, Any]:
    """Triggers the Librarian Agent to cluster and consolidate memories."""
    return await _librarian.run_cycle()


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
    return _service.create_memory_type(name, description, required_properties)


async def query_timeline(
    start: str,
    end: str,
    limit: int = 20,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Query entities within a time window, ordered chronologically."""
    from datetime import datetime  # noqa: PLC0415

    params = TemporalQueryParams(
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        limit=limit,
        project_id=project_id,
    )
    return await _service.query_timeline(params)


async def get_temporal_neighbors(
    entity_id: str,
    direction: str = "both",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find entities connected by temporal edges (before/after/both)."""
    return await _service.get_temporal_neighbors(entity_id, direction, limit)


async def get_bottles(
    limit: int = 10,
    search_text: str | None = None,
    before_date: str | None = None,
    after_date: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Query 'Message in a Bottle' entities — timestamped notes to your future self."""
    from datetime import datetime as dt  # noqa: PLC0415

    params = BottleQueryParams(
        limit=limit,
        search_text=search_text,
        before_date=dt.fromisoformat(before_date) if before_date else None,
        after_date=dt.fromisoformat(after_date) if after_date else None,
        project_id=project_id,
    )
    return await _service.get_bottles(params)


async def graph_health() -> dict[str, Any]:
    """Get graph health metrics: nodes, edges, density, orphans, communities, avg degree."""
    return await _service.get_graph_health()


async def find_knowledge_gaps(
    min_similarity: float = 0.7,
    max_edges: int = 2,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find structural gaps: clusters that are semantically similar but poorly connected."""
    params = GapDetectionParams(
        min_similarity=min_similarity,
        max_edges=max_edges,
        limit=limit,
    )
    return await _service.detect_structural_gaps(params)
