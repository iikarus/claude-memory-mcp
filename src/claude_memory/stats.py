"""Rolling-window search behaviour statistics — DRIFT-002.

Tracks per-search metrics in a deque for statistical drift detection.
The ``search_stats()`` MCP tool exposes the report to Claude Desktop.

Enabled by default.  Set ``SEARCH_STATS_ENABLED=false`` to disable.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SearchSnapshot:
    """Single search execution record."""

    timestamp: datetime
    query: str
    detected_intent: str
    retrieval_strategies: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    vector_scores: list[float | None] = field(default_factory=list)
    recency_scores: list[float] = field(default_factory=list)
    result_count: int = 0
    latency_ms: float = 0.0
    temporal_exhausted: bool | None = None


class SearchStatsAccumulator:
    """Rolling-window statistics for search behaviour monitoring."""

    def __init__(self, window_size: int | None = None) -> None:
        size = window_size or int(os.getenv("STATS_WINDOW_SIZE", "500"))
        self._window: deque[SearchSnapshot] = deque(maxlen=size)

    def record(self, snapshot: SearchSnapshot) -> None:
        """Append a search snapshot to the rolling window."""
        self._window.append(snapshot)

    def report(self) -> dict:  # type: ignore[type-arg]
        """Generate an aggregate report from the rolling window."""
        if not self._window:
            return {"status": "no data", "searches_recorded": 0}

        snapshots = list(self._window)
        total = len(snapshots)

        # Strategy distribution
        strategy_counts: dict[str, int] = {}
        for snap in snapshots:
            for s in snap.retrieval_strategies:
                strategy_counts[s] = strategy_counts.get(s, 0) + 1

        total_strategies = sum(strategy_counts.values()) or 1

        # Intent distribution
        intent_counts: dict[str, int] = {}
        for snap in snapshots:
            intent_counts[snap.detected_intent] = intent_counts.get(snap.detected_intent, 0) + 1

        # Score percentiles
        all_scores = sorted(sc for snap in snapshots for sc in snap.scores)

        # Vector score null rate
        all_vs = [vs for snap in snapshots for vs in snap.vector_scores]
        vs_null = sum(1 for vs in all_vs if vs is None)

        # Recency zero rate
        all_rec = [rs for snap in snapshots for rs in snap.recency_scores]
        rec_zero = sum(1 for rs in all_rec if rs == 0.0)

        # Temporal exhaustion rate
        temporal_snaps = [s for s in snapshots if s.temporal_exhausted is not None]
        temporal_exhausted = sum(1 for s in temporal_snaps if s.temporal_exhausted)

        # Latency percentiles
        latencies = sorted(s.latency_ms for s in snapshots)

        return {
            "searches_recorded": total,
            "window_start": snapshots[0].timestamp.isoformat(),
            "window_end": snapshots[-1].timestamp.isoformat(),
            "strategy_distribution": {
                k: {"count": v, "pct": round(v / total_strategies * 100, 1)}
                for k, v in sorted(strategy_counts.items(), key=lambda x: -x[1])
            },
            "intent_distribution": {
                k: {"count": v, "pct": round(v / total * 100, 1)}
                for k, v in sorted(intent_counts.items(), key=lambda x: -x[1])
            },
            "score_percentiles": (
                {
                    "p10": _percentile(all_scores, 10),
                    "p50": _percentile(all_scores, 50),
                    "p90": _percentile(all_scores, 90),
                }
                if all_scores
                else {}
            ),
            "vector_score_null_rate_pct": (
                round(vs_null / len(all_vs) * 100, 1) if all_vs else 0.0
            ),
            "recency_score_zero_rate_pct": (
                round(rec_zero / len(all_rec) * 100, 1) if all_rec else 0.0
            ),
            "temporal_exhaustion_rate_pct": (
                round(temporal_exhausted / len(temporal_snaps) * 100, 1) if temporal_snaps else None
            ),
            "latency_ms_percentiles": {
                "p50": _percentile(latencies, 50),
                "p90": _percentile(latencies, 90),
                "p99": _percentile(latencies, 99),
            },
            "avg_result_count": round(sum(s.result_count for s in snapshots) / total, 1),
        }


def _percentile(sorted_list: list[float], pct: int) -> float:
    """Compute a percentile from a pre-sorted list."""
    if not sorted_list:
        return 0.0
    idx = int(len(sorted_list) * pct / 100)
    idx = min(idx, len(sorted_list) - 1)
    return round(sorted_list[idx], 4)


def create_accumulator() -> SearchStatsAccumulator | None:
    """Factory: returns an accumulator if stats are enabled (default: on)."""
    if os.getenv("SEARCH_STATS_ENABLED", "true").lower() == "false":
        return None
    return SearchStatsAccumulator()


def record_search(  # noqa: PLR0913
    accumulator: SearchStatsAccumulator | None,
    *,
    query: str,
    detected_intent: str,
    results: list,  # type: ignore[type-arg]
    latency_ms: float = 0.0,
    temporal_exhausted: bool | None = None,
) -> None:
    """Record a search snapshot if the accumulator is active."""
    if accumulator is None:
        return
    accumulator.record(
        SearchSnapshot(
            timestamp=datetime.now(UTC),
            query=query,
            detected_intent=detected_intent,
            retrieval_strategies=[getattr(r, "retrieval_strategy", "unknown") for r in results],
            scores=[getattr(r, "score", 0.0) for r in results],
            vector_scores=[getattr(r, "vector_score", None) for r in results],
            recency_scores=[getattr(r, "recency_score", 0.0) for r in results],
            result_count=len(results),
            latency_ms=latency_ms,
            temporal_exhausted=temporal_exhausted,
        )
    )
