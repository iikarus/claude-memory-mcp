"""Tests for vector_store.py — coverage gap remediation.

Covers uncovered async methods:
  - search
  - retrieve_by_ids
  - search_mmr
  - delete
  - count
  - list_ids
  - _build_filter
  - _cosine_similarity
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from claude_memory.vector_store import QdrantVectorStore

# ─── Helpers ────────────────────────────────────────────────────────


def _make_store() -> QdrantVectorStore:
    """Create a QdrantVectorStore with mocked client."""
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store.client = AsyncMock()
    store.collection = "test_collection"
    store.vector_size = 3
    store._initialized = True
    return store


def _scored_point(
    pid: str, score: float, payload: dict | None = None, vector: list | None = None
) -> SimpleNamespace:
    """Create a mock ScoredPoint."""
    return SimpleNamespace(id=pid, score=score, payload=payload or {}, vector=vector)


def _point_with_vector(pid: str, vector: list[float]) -> SimpleNamespace:
    """Create a mock point with a vector (for retrieve_by_ids)."""
    return SimpleNamespace(id=pid, vector=vector)


# ═══════════════════════════════════════════════════════════════
#  search
# ═══════════════════════════════════════════════════════════════


class TestSearch:
    """3e/1s/1h for search."""

    @pytest.mark.asyncio()
    async def test_happy_returns_results(self) -> None:
        """Happy: returns formatted search results."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(
            points=[_scored_point("a", 0.95, {"name": "Alice"})]
        )

        results = await store.search([0.1, 0.2, 0.3])
        assert len(results) == 1
        assert results[0]["_id"] == "a"
        assert results[0]["_score"] == 0.95
        assert results[0]["payload"]["name"] == "Alice"

    @pytest.mark.asyncio()
    async def test_happy_with_filter(self) -> None:
        """Happy: filter dict is converted and passed to Qdrant."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(points=[_scored_point("b", 0.8)])

        results = await store.search([0.1, 0.2, 0.3], filter={"project_id": "proj-1"})
        assert len(results) == 1
        # Verify query_filter was passed
        call_kwargs = store.client.query_points.call_args[1]
        assert call_kwargs["query_filter"] is not None

    @pytest.mark.asyncio()
    async def test_sad_empty_results(self) -> None:
        """Sad: no matches returns empty list."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(points=[])

        results = await store.search([0.1, 0.2, 0.3])
        assert results == []

    @pytest.mark.asyncio()
    async def test_evil_null_payload(self) -> None:
        """Evil: point with None payload gets empty dict."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(
            points=[_scored_point("c", 0.7, payload=None)]
        )

        results = await store.search([0.1, 0.2, 0.3])
        assert results[0]["payload"] == {}


# ═══════════════════════════════════════════════════════════════
#  retrieve_by_ids
# ═══════════════════════════════════════════════════════════════


class TestRetrieveByIds:
    """3e/1s/1h for retrieve_by_ids."""

    @pytest.mark.asyncio()
    async def test_happy_computes_cosine(self) -> None:
        """Happy: retrieves points and computes cosine similarity."""
        store = _make_store()
        # Identical vectors → cosine = 1.0
        store.client.retrieve.return_value = [_point_with_vector("a", [0.1, 0.2, 0.3])]

        scores = await store.retrieve_by_ids(["a"], [0.1, 0.2, 0.3])
        assert "a" in scores
        assert scores["a"] == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_sad_empty_ids(self) -> None:
        """Sad: empty ID list returns empty dict immediately."""
        store = _make_store()

        scores = await store.retrieve_by_ids([], [0.1, 0.2, 0.3])
        assert scores == {}
        store.client.retrieve.assert_not_called()

    @pytest.mark.asyncio()
    async def test_evil_zero_query_vector(self) -> None:
        """Evil: zero-magnitude query vector returns 0.0 for all points."""
        store = _make_store()
        store.client.retrieve.return_value = [_point_with_vector("a", [0.1, 0.2, 0.3])]

        scores = await store.retrieve_by_ids(["a"], [0.0, 0.0, 0.0])
        assert scores["a"] == 0.0

    @pytest.mark.asyncio()
    async def test_evil_zero_point_vector(self) -> None:
        """Evil: zero-magnitude point vector gets score 0.0."""
        store = _make_store()
        store.client.retrieve.return_value = [_point_with_vector("a", [0.0, 0.0, 0.0])]

        scores = await store.retrieve_by_ids(["a"], [0.1, 0.2, 0.3])
        assert scores["a"] == 0.0

    @pytest.mark.asyncio()
    async def test_evil_none_vector_skipped(self) -> None:
        """Evil: point with None vector is skipped."""
        store = _make_store()
        store.client.retrieve.return_value = [SimpleNamespace(id="a", vector=None)]

        scores = await store.retrieve_by_ids(["a"], [0.1, 0.2, 0.3])
        assert "a" not in scores


# ═══════════════════════════════════════════════════════════════
#  search_mmr
# ═══════════════════════════════════════════════════════════════


class TestSearchMMR:
    """3e/1s/1h for search_mmr."""

    @pytest.mark.asyncio()
    async def test_happy_returns_diverse_results(self) -> None:
        """Happy: MMR returns re-ranked diverse results."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(
            points=[
                _scored_point("a", 0.95, vector=[1.0, 0.0, 0.0]),
                _scored_point("b", 0.90, vector=[0.0, 1.0, 0.0]),
                _scored_point("c", 0.85, vector=[0.99, 0.01, 0.0]),
            ]
        )

        results = await store.search_mmr([1.0, 0.0, 0.0], limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio()
    async def test_sad_empty_results(self) -> None:
        """Sad: no candidates returns empty list."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(points=[])

        results = await store.search_mmr([0.1, 0.2, 0.3])
        assert results == []

    @pytest.mark.asyncio()
    async def test_evil_single_candidate(self) -> None:
        """Evil: single candidate returned as-is."""
        store = _make_store()
        store.client.query_points.return_value = SimpleNamespace(
            points=[_scored_point("a", 0.95, vector=[1.0, 0.0, 0.0])]
        )

        results = await store.search_mmr([1.0, 0.0, 0.0], limit=5)
        assert len(results) == 1
        assert results[0]["_id"] == "a"


# ═══════════════════════════════════════════════════════════════
#  delete, count, list_ids
# ═══════════════════════════════════════════════════════════════


class TestDelete:
    """Tests for delete."""

    @pytest.mark.asyncio()
    async def test_happy_deletes_point(self) -> None:
        """Happy: deletes a vector by ID."""
        store = _make_store()
        store.client.delete.return_value = None

        await store.delete("entity-1")
        store.client.delete.assert_called_once()


class TestCount:
    """Tests for count."""

    @pytest.mark.asyncio()
    async def test_happy_returns_count(self) -> None:
        """Happy: returns points_count from collection info."""
        store = _make_store()
        store.client.get_collection.return_value = SimpleNamespace(points_count=42)

        result = await store.count()
        assert result == 42

    @pytest.mark.asyncio()
    async def test_evil_none_points_count(self) -> None:
        """Evil: None points_count returns 0."""
        store = _make_store()
        store.client.get_collection.return_value = SimpleNamespace(points_count=None)

        result = await store.count()
        assert result == 0


class TestListIds:
    """Tests for list_ids."""

    @pytest.mark.asyncio()
    async def test_happy_scrolls_all_ids(self) -> None:
        """Happy: scrolls through pages and returns all IDs."""
        store = _make_store()
        store.client.scroll.side_effect = [
            ([SimpleNamespace(id="id-1"), SimpleNamespace(id="id-2")], "next"),
            ([SimpleNamespace(id="id-3")], None),
        ]

        result = await store.list_ids()
        assert result == ["id-1", "id-2", "id-3"]

    @pytest.mark.asyncio()
    async def test_sad_empty_collection(self) -> None:
        """Sad: empty collection returns empty list."""
        store = _make_store()
        store.client.scroll.return_value = ([], None)

        result = await store.list_ids()
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  _build_filter + _cosine_similarity
# ═══════════════════════════════════════════════════════════════


class TestBuildFilter:
    """Tests for _build_filter."""

    def test_happy_match_value(self) -> None:
        """Happy: string value creates MatchValue condition."""
        store = _make_store()
        result = store._build_filter({"project_id": "proj-1"})
        assert result is not None

    def test_happy_created_at_lt_iso(self) -> None:
        """Happy: created_at_lt with ISO string creates Range condition."""
        store = _make_store()
        result = store._build_filter({"created_at_lt": "2026-01-01T00:00:00"})
        assert result is not None

    def test_happy_created_at_lt_numeric(self) -> None:
        """Happy: created_at_lt with numeric string creates Range."""
        store = _make_store()
        result = store._build_filter({"created_at_lt": "1234567890.0"})
        assert result is not None

    def test_sad_none_filter(self) -> None:
        """Sad: None filter returns None."""
        store = _make_store()
        result = store._build_filter(None)
        assert result is None

    def test_sad_empty_filter(self) -> None:
        """Sad: empty dict returns None."""
        store = _make_store()
        result = store._build_filter({})
        assert result is None


class TestCosineSimilarity:
    """Tests for _cosine_similarity."""

    def test_happy_identical_vectors(self) -> None:
        """Happy: identical vectors → similarity = 1.0."""
        result = QdrantVectorStore._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert result == pytest.approx(1.0)

    def test_evil_non_list_input(self) -> None:
        """Evil: non-list input returns 0.0."""
        result = QdrantVectorStore._cosine_similarity("not a list", [1.0, 0.0])
        assert result == 0.0

    def test_evil_zero_magnitude(self) -> None:
        """Evil: zero magnitude vector returns 0.0."""
        result = QdrantVectorStore._cosine_similarity([0.0, 0.0], [1.0, 0.0])
        assert result == 0.0
