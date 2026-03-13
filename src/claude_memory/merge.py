"""Reciprocal Rank Fusion (RRF) merge for hybrid search — ADR-007.

Merges ranked lists from vector search and graph queries without
score normalisation.  Pure logic module with no I/O dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MergedResult:
    """Internal merge output — not exposed via MCP."""

    entity_id: str
    rrf_score: float
    vector_score: float | None = None  # None if graph-only
    vector_rank: int | None = None
    graph_rank: int | None = None
    graph_metadata: dict[str, Any] = field(default_factory=dict)
    retrieval_sources: list[str] = field(default_factory=list)


def rrf_merge(
    vector_results: list[dict[str, Any]],
    graph_results: list[dict[str, Any]],
    *,
    k: int = 60,
    limit: int = 10,
) -> list[MergedResult]:
    """Reciprocal Rank Fusion merge of vector and graph result lists.

    For each entity ``e`` appearing in any result list::

        rrf_score(e) = Σ  1 / (k + rank_i(e))
                        i∈sources

    Args:
        vector_results: ``[{"_id": str, "_score": float, ...}]`` from Qdrant.
        graph_results: ``[{"id": str, ...}]`` from graph queries.
        k: RRF constant (default 60) — dampens top-rank dominance.
        limit: Maximum results to return.

    Returns:
        Merged results sorted by RRF score descending, capped at *limit*.
    """
    scores: dict[str, float] = {}
    vector_ranks: dict[str, int] = {}
    vector_scores: dict[str, float] = {}
    graph_ranks: dict[str, int] = {}
    graph_meta: dict[str, dict[str, Any]] = {}
    sources: dict[str, list[str]] = {}

    # Process vector results (1-indexed ranks)
    for rank, vr in enumerate(vector_results, start=1):
        eid = vr["_id"]
        scores[eid] = scores.get(eid, 0.0) + 1.0 / (k + rank)
        vector_ranks[eid] = rank
        vector_scores[eid] = vr.get("_score", 0.0)
        sources.setdefault(eid, []).append("vector")

    # Process graph results (1-indexed ranks)
    for rank, gr in enumerate(graph_results, start=1):
        eid = gr.get("id", "")
        if not eid:
            continue
        scores[eid] = scores.get(eid, 0.0) + 1.0 / (k + rank)
        graph_ranks[eid] = rank
        # Preserve all graph metadata (minus the id itself)
        graph_meta[eid] = {gk: gv for gk, gv in gr.items() if gk != "id"}
        sources.setdefault(eid, []).append("graph")

    # Sort by RRF score descending, cap at limit
    sorted_ids = sorted(scores, key=lambda eid: scores[eid], reverse=True)[:limit]

    return [
        MergedResult(
            entity_id=eid,
            rrf_score=scores[eid],
            vector_score=vector_scores.get(eid),
            vector_rank=vector_ranks.get(eid),
            graph_rank=graph_ranks.get(eid),
            graph_metadata=graph_meta.get(eid, {}),
            retrieval_sources=sources.get(eid, []),
        )
        for eid in sorted_ids
    ]
