"""Adaptive query routing — rule-based intent classification and dispatch.

Routes queries to the optimal retrieval strategy based on keyword patterns.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from claude_memory.schema import TemporalQueryParams

if TYPE_CHECKING:  # pragma: no cover
    from claude_memory.tools import MemoryService

_MIN_QUOTED_ENTITIES = 2

logger = logging.getLogger(__name__)


class QueryIntent(StrEnum):
    """Classified intent of a user query."""

    SEMANTIC = "semantic"
    ASSOCIATIVE = "associative"
    TEMPORAL = "temporal"
    RELATIONAL = "relational"


# ── Keyword patterns (compiled once at import time) ─────────────────

_TEMPORAL_KEYWORDS: list[str] = [
    "when",
    "timeline",
    "chronolog",
    "history of",
    "last week",
    "last month",
    "yesterday",
    "before",
    "after",
    "recent",
    "earliest",
    "latest",
    "over time",
    "sequence",
]

_RELATIONAL_KEYWORDS: list[str] = [
    "connect",
    "path between",
    "link between",
    "bridge",
    "relationship between",
    "how does .+ relate to",
    "what connects",
]

_ASSOCIATIVE_KEYWORDS: list[str] = [
    "associated with",
    "related to",
    "similar to",
    "reminds me of",
    "in the context of",
    "neighbourhood of",
    "neighborhood of",
    "cluster around",
    "spreading",
]

_TEMPORAL_RE = re.compile(
    "|".join(re.escape(k) if "." not in k else k for k in _TEMPORAL_KEYWORDS),
    re.IGNORECASE,
)
_RELATIONAL_RE = re.compile(
    "|".join(k for k in _RELATIONAL_KEYWORDS),
    re.IGNORECASE,
)
_ASSOCIATIVE_RE = re.compile(
    "|".join(k for k in _ASSOCIATIVE_KEYWORDS),
    re.IGNORECASE,
)


class QueryRouter:
    """Rule-based query router — classifies intent and dispatches to strategy."""

    def classify(self, query: str) -> QueryIntent:
        """Classify the intent of a natural-language query.

        Priority order: TEMPORAL > RELATIONAL > ASSOCIATIVE > SEMANTIC.
        """
        if not query:
            return QueryIntent.SEMANTIC

        # 1. Temporal — strongest signal
        if _TEMPORAL_RE.search(query):
            return QueryIntent.TEMPORAL

        # 2. Relational — mentions connections between things
        if _RELATIONAL_RE.search(query):
            return QueryIntent.RELATIONAL

        # 3. Associative — context / neighbourhood queries
        if _ASSOCIATIVE_RE.search(query):
            return QueryIntent.ASSOCIATIVE

        # 4. Default: semantic vector search
        return QueryIntent.SEMANTIC

    async def route(  # noqa: PLR0913
        self,
        query: str,
        service: MemoryService,
        *,
        intent: QueryIntent | None = None,
        limit: int = 10,
        project_id: str | None = None,
        temporal_window_days: int = 7,
        **kwargs: Any,
    ) -> list[Any]:
        """Dispatch query to the appropriate retrieval strategy.

        Args:
            query: The natural-language query string.
            service: MemoryService providing all retrieval backends.
            intent: Optional override — skips auto-classification.
            limit: Maximum results to return.
            project_id: Optional project scope.
            temporal_window_days: Lookback window for temporal queries (default 7).
            **kwargs: Extra params forwarded to the underlying method.

        Returns:
            List of results from the selected strategy.
        """
        if not query:
            return []

        resolved_intent = intent or self.classify(query)
        logger.info("Routing query to %s strategy", resolved_intent.value)

        if resolved_intent == QueryIntent.TEMPORAL:
            return await self._route_temporal(
                service, query, limit, project_id, temporal_window_days
            )

        if resolved_intent == QueryIntent.RELATIONAL:
            return await self._route_relational(service, query)

        if resolved_intent == QueryIntent.ASSOCIATIVE:
            return await self._route_associative(service, query, limit, project_id, **kwargs)

        # Default: SEMANTIC
        return await service.search(query, limit=limit, project_id=project_id, **kwargs)

    # ── Private dispatch helpers ─────────────────────────────────────

    @staticmethod
    async def _route_temporal(
        service: MemoryService,
        query: str,
        limit: int,
        project_id: str | None,
        temporal_window_days: int = 7,
    ) -> list[Any]:
        """Route to timeline query with parameterised window.

        Since temporal queries from natural language rarely include exact
        date ranges, we default to the last ``temporal_window_days`` days.
        """
        now = datetime.now(UTC)
        params = TemporalQueryParams(
            start=now - timedelta(days=temporal_window_days),
            end=now,
            limit=limit,
            project_id=project_id,
        )
        return await service.query_timeline(params)

    @staticmethod
    async def _route_relational(
        service: MemoryService,
        query: str,
    ) -> list[Any]:
        """Route to graph traversal.

        Attempts to extract two entity references from the query.
        Falls back to semantic search if entity extraction fails.
        """
        # Simple heuristic: find quoted strings or CamelCase words
        quoted = re.findall(r'"([^"]+)"', query)
        if len(quoted) >= _MIN_QUOTED_ENTITIES:
            return await service.traverse_path(quoted[0], quoted[1])

        # Fallback: semantic search (we can't reliably extract entities)
        return await service.search(query, limit=10)

    @staticmethod
    async def _route_associative(
        service: MemoryService,
        query: str,
        limit: int,
        project_id: str | None,
        **kwargs: Any,
    ) -> list[Any]:
        """Route to spreading-activation search."""
        return await service.search_associative(query, limit=limit, project_id=project_id, **kwargs)
