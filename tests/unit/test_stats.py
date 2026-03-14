"""Tests for stats.py — 3 evil / 1 sad / 1 happy + accumulator tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from claude_memory.stats import (
    SearchSnapshot,
    SearchStatsAccumulator,
    _percentile,
    create_accumulator,
    record_search,
)


def _snapshot(  # noqa: PLR0913
    query: str = "test",
    intent: str = "semantic",
    strategies: list[str] | None = None,
    scores: list[float] | None = None,
    vector_scores: list[float | None] | None = None,
    recency_scores: list[float] | None = None,
    result_count: int = 3,
    latency_ms: float = 50.0,
    temporal_exhausted: bool | None = None,
) -> SearchSnapshot:
    """Factory for test snapshots."""
    return SearchSnapshot(
        timestamp=datetime.now(UTC),
        query=query,
        detected_intent=intent,
        retrieval_strategies=strategies or ["semantic"],
        scores=scores or [0.5, 0.6, 0.7],
        vector_scores=vector_scores or [0.5, 0.6, 0.7],
        recency_scores=recency_scores or [0.3, 0.2, 0.1],
        result_count=result_count,
        latency_ms=latency_ms,
        temporal_exhausted=temporal_exhausted,
    )


# ─── Evil Path Tests ────────────────────────────────────────


class TestStatsEvil:
    """Adversarial inputs."""

    def test_evil_empty_report(self) -> None:
        """Empty accumulator must return 'no data', not crash."""
        acc = SearchStatsAccumulator(window_size=10)
        report = acc.report()
        assert report["status"] == "no data"
        assert report["searches_recorded"] == 0

    def test_evil_window_overflow_drops_oldest(self) -> None:
        """When window overflows, oldest entries must be dropped."""
        acc = SearchStatsAccumulator(window_size=2)
        acc.record(_snapshot(query="old1"))
        acc.record(_snapshot(query="old2"))
        acc.record(_snapshot(query="new"))
        report = acc.report()
        assert report["searches_recorded"] == 2

    def test_evil_all_none_vector_scores(self) -> None:
        """100% null vector scores must give 100% null rate, not crash."""
        acc = SearchStatsAccumulator(window_size=10)
        acc.record(_snapshot(vector_scores=[None, None, None]))
        report = acc.report()
        assert report["vector_score_null_rate_pct"] == 100.0


# ─── Sad Path Test ──────────────────────────────────────────


class TestStatsSad:
    """Expected edge conditions."""

    def test_sad_single_entry_percentiles(self) -> None:
        """Single entry must produce valid percentiles."""
        acc = SearchStatsAccumulator(window_size=10)
        acc.record(_snapshot(scores=[0.42]))
        report = acc.report()
        assert report["score_percentiles"]["p50"] == 0.42
        assert report["avg_result_count"] == 3


# ─── Happy Path Test ────────────────────────────────────────


class TestStatsHappy:
    """Normal operations."""

    def test_happy_full_report(self) -> None:
        """A populated accumulator must produce a complete report."""
        acc = SearchStatsAccumulator(window_size=100)
        acc.record(_snapshot(intent="semantic", strategies=["semantic"]))
        acc.record(_snapshot(intent="temporal", strategies=["hybrid"], temporal_exhausted=True))
        acc.record(_snapshot(intent="temporal", strategies=["temporal"], temporal_exhausted=False))

        report = acc.report()
        assert report["searches_recorded"] == 3
        assert "semantic" in report["strategy_distribution"]
        assert "temporal" in report["intent_distribution"]
        assert report["temporal_exhaustion_rate_pct"] == 50.0
        assert "p50" in report["latency_ms_percentiles"]


# ─── Factory / Helper Tests ─────────────────────────────────


class TestCreateAccumulator:
    """Factory function tests."""

    def test_default_creates_accumulator(self) -> None:
        """Default (no env var) should create an accumulator."""
        with patch.dict("os.environ", {}, clear=False):
            acc = create_accumulator()
            assert acc is not None

    def test_disabled_returns_none(self) -> None:
        """SEARCH_STATS_ENABLED=false must return None."""
        with patch.dict("os.environ", {"SEARCH_STATS_ENABLED": "false"}):
            acc = create_accumulator()
            assert acc is None


class TestRecordSearch:
    """record_search() helper tests."""

    def test_record_with_none_accumulator_is_noop(self) -> None:
        """Passing None accumulator must not crash."""
        record_search(None, query="x", detected_intent="semantic", results=[])

    def test_record_appends_snapshot(self) -> None:
        """A valid call must add one snapshot."""
        acc = SearchStatsAccumulator(window_size=10)
        record_search(acc, query="test", detected_intent="semantic", results=[])
        assert acc.report()["searches_recorded"] == 1


class TestPercentile:
    """Edge cases for _percentile."""

    def test_empty_list(self) -> None:
        assert _percentile([], 50) == 0.0

    def test_single_element(self) -> None:
        assert _percentile([0.5], 50) == 0.5

    def test_all_same_values(self) -> None:
        assert _percentile([0.3, 0.3, 0.3], 90) == 0.3
