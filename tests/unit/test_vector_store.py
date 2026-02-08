"""Tests for the QdrantVectorStore (vector_store.py).

Covers: init, _ensure_collection, upsert, search, delete.
All Qdrant client methods are mocked — no actual Qdrant server needed.
"""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Test Constants ─────────────────────────────────────────────────

COLLECTION_NAME = "memory_embeddings"
VECTOR_SIZE = 1024
CUSTOM_HOST = "qdrant-host"
CUSTOM_PORT = 7333
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 6333
SEARCH_LIMIT = 5

POINT_ID = "point-001"
POINT_VECTOR = [0.1, 0.2, 0.3]
POINT_PAYLOAD: dict[str, Any] = {"name": "test-entity", "project_id": "project-alpha"}
POINT_SCORE = 0.95

FILTER_PROJECT_ID_KEY = "project_id"
FILTER_PROJECT_ID_VALUE = "project-alpha"
FILTER_CREATED_AT_KEY = "created_at_lt"
FILTER_CREATED_AT_EPOCH = 1717200000


# ─── Module Import ──────────────────────────────────────────────────

with patch("claude_memory.vector_store.AsyncQdrantClient"):
    from claude_memory.vector_store import QdrantVectorStore


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def mock_qdrant_client() -> AsyncMock:
    """Creates a fully mocked AsyncQdrantClient."""
    client = AsyncMock()

    # get_collections returns a list with one matching collection
    collection_info = MagicMock()
    collection_info.name = COLLECTION_NAME
    collections_response = MagicMock()
    collections_response.collections = [collection_info]
    client.get_collections.return_value = collections_response

    # query_points returns scored points
    scored_point = MagicMock()
    scored_point.id = POINT_ID
    scored_point.score = POINT_SCORE
    scored_point.payload = POINT_PAYLOAD
    query_response = MagicMock()
    query_response.points = [scored_point]
    client.query_points.return_value = query_response

    return client


@pytest.fixture()
def store(mock_qdrant_client: AsyncMock) -> QdrantVectorStore:
    """Creates a QdrantVectorStore with a mocked client."""
    with patch("claude_memory.vector_store.AsyncQdrantClient", return_value=mock_qdrant_client):
        s = QdrantVectorStore(host=CUSTOM_HOST, port=CUSTOM_PORT)
    return s


# ─── Protocol Compliance Tests ──────────────────────────────────────


def test_qdrant_implements_vector_store_protocol() -> None:
    """QdrantVectorStore has the methods required by VectorStore protocol."""
    assert hasattr(QdrantVectorStore, "upsert")
    assert hasattr(QdrantVectorStore, "search")
    assert hasattr(QdrantVectorStore, "delete")


# ─── Constructor Tests ──────────────────────────────────────────────


def test_init_with_custom_params() -> None:
    with patch("claude_memory.vector_store.AsyncQdrantClient"):
        store = QdrantVectorStore(host=CUSTOM_HOST, port=CUSTOM_PORT)
        assert store.host == CUSTOM_HOST
        assert store.port == CUSTOM_PORT
        assert store.collection == COLLECTION_NAME
        assert store.vector_size == VECTOR_SIZE
        assert store._initialized is False


def test_init_from_env() -> None:
    with patch("claude_memory.vector_store.AsyncQdrantClient"):
        with patch.dict(os.environ, {"QDRANT_HOST": CUSTOM_HOST, "QDRANT_PORT": str(CUSTOM_PORT)}):
            store = QdrantVectorStore()
            assert store.host == CUSTOM_HOST
            assert store.port == CUSTOM_PORT


def test_init_defaults() -> None:
    with patch("claude_memory.vector_store.AsyncQdrantClient"):
        store = QdrantVectorStore()
        assert store.host == DEFAULT_HOST
        assert store.port == DEFAULT_PORT


# ─── _ensure_collection Tests ───────────────────────────────────────


async def test_ensure_collection_already_exists(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    """When collection exists, don't create it."""
    await store._ensure_collection()
    assert store._initialized is True
    mock_qdrant_client.create_collection.assert_not_awaited()


async def test_ensure_collection_creates_when_missing(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    """When collection doesn't exist, create it."""
    mock_qdrant_client.get_collections.return_value.collections = []
    await store._ensure_collection()
    mock_qdrant_client.create_collection.assert_awaited_once()
    assert store._initialized is True


async def test_ensure_collection_skips_if_initialized(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    """Once initialized, skip the check entirely."""
    store._initialized = True
    await store._ensure_collection()
    mock_qdrant_client.get_collections.assert_not_awaited()


async def test_ensure_collection_handles_error(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    """Connection errors are logged and re-raised."""
    mock_qdrant_client.get_collections.side_effect = ConnectionError("no connection")
    with pytest.raises(ConnectionError, match="no connection"):
        await store._ensure_collection()
    assert store._initialized is False  # Still not initialized


# ─── upsert Tests ───────────────────────────────────────────────────


async def test_upsert(store: QdrantVectorStore, mock_qdrant_client: AsyncMock) -> None:
    await store.upsert(id=POINT_ID, vector=POINT_VECTOR, payload=POINT_PAYLOAD)
    mock_qdrant_client.upsert.assert_awaited_once()
    call_kwargs = mock_qdrant_client.upsert.call_args[1]
    assert call_kwargs["collection_name"] == COLLECTION_NAME


# ─── search Tests ───────────────────────────────────────────────────


async def test_search_no_filter(store: QdrantVectorStore, mock_qdrant_client: AsyncMock) -> None:
    results = await store.search(vector=POINT_VECTOR, limit=SEARCH_LIMIT)
    assert len(results) == 1
    assert results[0]["_id"] == POINT_ID
    assert results[0]["_score"] == POINT_SCORE
    assert results[0]["payload"] == POINT_PAYLOAD


async def test_search_with_match_filter(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    filter_dict = {FILTER_PROJECT_ID_KEY: FILTER_PROJECT_ID_VALUE}
    await store.search(vector=POINT_VECTOR, limit=SEARCH_LIMIT, filter=filter_dict)
    call_kwargs = mock_qdrant_client.query_points.call_args[1]
    assert call_kwargs["query_filter"] is not None


async def test_search_with_range_filter(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    filter_dict = {FILTER_CREATED_AT_KEY: FILTER_CREATED_AT_EPOCH}
    await store.search(vector=POINT_VECTOR, limit=SEARCH_LIMIT, filter=filter_dict)
    call_kwargs = mock_qdrant_client.query_points.call_args[1]
    assert call_kwargs["query_filter"] is not None


async def test_search_empty_results(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    mock_qdrant_client.query_points.return_value.points = []
    results = await store.search(vector=POINT_VECTOR, limit=SEARCH_LIMIT)
    assert results == []


async def test_search_null_payload(store: QdrantVectorStore, mock_qdrant_client: AsyncMock) -> None:
    """When point.payload is None, return empty dict."""
    point = MagicMock()
    point.id = POINT_ID
    point.score = POINT_SCORE
    point.payload = None
    mock_qdrant_client.query_points.return_value.points = [point]
    results = await store.search(vector=POINT_VECTOR, limit=SEARCH_LIMIT)
    assert results[0]["payload"] == {}


# ─── delete Tests ───────────────────────────────────────────────────


async def test_delete(store: QdrantVectorStore, mock_qdrant_client: AsyncMock) -> None:
    await store.delete(id=POINT_ID)
    mock_qdrant_client.delete.assert_awaited_once()


# ─── Branch Coverage Tests ──────────────────────────────────────────

FILTER_UNSUPPORTED_KEY = "tags"
FILTER_UNSUPPORTED_VALUE = ["tag-a", "tag-b"]  # list is not str/int/float/bool


async def test_search_with_unsupported_filter_type(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    """Branch 96→89: filter value is not str/int/float/bool, elif skipped."""
    mock_scored_point = MagicMock()
    mock_scored_point.id = POINT_ID
    mock_scored_point.score = POINT_SCORE
    mock_scored_point.payload = POINT_PAYLOAD
    mock_qdrant_client.query_points.return_value = MagicMock(points=[mock_scored_point])

    # Pass a filter with a list value → neither 'created_at_lt' nor scalar match
    results = await store.search(
        vector=POINT_VECTOR,
        limit=SEARCH_LIMIT,
        filter={FILTER_UNSUPPORTED_KEY: FILTER_UNSUPPORTED_VALUE},
    )
    assert len(results) == 1


async def test_search_with_all_unsupported_filters(
    store: QdrantVectorStore, mock_qdrant_client: AsyncMock
) -> None:
    """Branch 101→106: all filter values unsupported → empty conditions → no filter built."""
    mock_scored_point = MagicMock()
    mock_scored_point.id = POINT_ID
    mock_scored_point.score = POINT_SCORE
    mock_scored_point.payload = POINT_PAYLOAD
    mock_qdrant_client.query_points.return_value = MagicMock(points=[mock_scored_point])

    # Both filters have unsupported types
    results = await store.search(
        vector=POINT_VECTOR,
        limit=SEARCH_LIMIT,
        filter={
            FILTER_UNSUPPORTED_KEY: FILTER_UNSUPPORTED_VALUE,
            "nested": {"key": "value"},
        },
    )
    assert len(results) == 1
    # Verify query_filter was None (no valid conditions)
    call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is None


# ─── MMR Search Tests ───────────────────────────────────────────────


def _make_scored_points(scores: list[float]) -> list[MagicMock]:
    """Helper to create scored point mocks with distinct vectors."""
    points = []
    for i, score in enumerate(scores):
        pt = MagicMock()
        pt.id = f"point-{i:03d}"
        pt.score = score
        pt.payload = {"name": f"entity-{i}", "project_id": "project-alpha"}
        # Distinct vector per point (for MMR diversity calc)
        pt.vector = [float(i) / 10.0] * 3
        points.append(pt)
    return points


async def test_search_mmr_returns_diverse_results(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """MMR search re-ranks for diversity — top result is the same, rest may differ."""
    # 6 points with decreasing similarity
    points = _make_scored_points([0.99, 0.98, 0.97, 0.80, 0.75, 0.70])
    query_response = MagicMock()
    query_response.points = points
    mock_qdrant_client.query_points.return_value = query_response

    results = await store.search_mmr(vector=POINT_VECTOR, limit=3, mmr_lambda=0.5)

    # Should return exactly `limit` results
    assert len(results) == 3
    # Each result has expected keys
    for r in results:
        assert "_id" in r
        assert "_score" in r
        assert "payload" in r


async def test_search_mmr_empty_results(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """MMR search with no results returns empty list."""
    query_response = MagicMock()
    query_response.points = []
    mock_qdrant_client.query_points.return_value = query_response

    results = await store.search_mmr(vector=POINT_VECTOR, limit=3)
    assert results == []


async def test_search_mmr_fewer_than_limit(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """MMR search with fewer candidates than limit returns all of them."""
    points = _make_scored_points([0.95, 0.85])
    query_response = MagicMock()
    query_response.points = points
    mock_qdrant_client.query_points.return_value = query_response

    results = await store.search_mmr(vector=POINT_VECTOR, limit=10)
    assert len(results) == 2


async def test_search_mmr_lambda_one_equals_similarity(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """With mmr_lambda=1.0, MMR degenerates to pure similarity ranking."""
    points = _make_scored_points([0.99, 0.90, 0.80])
    query_response = MagicMock()
    query_response.points = points
    mock_qdrant_client.query_points.return_value = query_response

    results = await store.search_mmr(vector=POINT_VECTOR, limit=3, mmr_lambda=1.0)
    # Pure similarity → same order as original
    assert results[0]["_id"] == "point-000"
    assert results[1]["_id"] == "point-001"
    assert results[2]["_id"] == "point-002"


async def test_search_mmr_with_filter(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """MMR search passes filter through to query_points."""
    points = _make_scored_points([0.95])
    query_response = MagicMock()
    query_response.points = points
    mock_qdrant_client.query_points.return_value = query_response

    filter_dict = {FILTER_PROJECT_ID_KEY: FILTER_PROJECT_ID_VALUE}
    results = await store.search_mmr(vector=POINT_VECTOR, limit=5, filter=filter_dict)
    assert len(results) == 1
    call_kwargs = mock_qdrant_client.query_points.call_args[1]
    assert call_kwargs["query_filter"] is not None


async def test_search_mmr_single_result(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """MMR with a single candidate just returns it directly."""
    points = _make_scored_points([0.95])
    query_response = MagicMock()
    query_response.points = points
    mock_qdrant_client.query_points.return_value = query_response

    results = await store.search_mmr(vector=POINT_VECTOR, limit=5)
    assert len(results) == 1
    assert results[0]["_id"] == "point-000"


# ─── HNSW Indexing Threshold Tests ──────────────────────────────────


async def test_ensure_collection_creates_with_hnsw_config(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """New collection should be created with custom HNSW config (low threshold)."""
    mock_qdrant_client.get_collections.return_value.collections = []
    await store._ensure_collection()
    call_kwargs = mock_qdrant_client.create_collection.call_args[1]
    # Should have hnsw_config with our custom indexing_threshold
    assert "hnsw_config" in call_kwargs
    assert call_kwargs["hnsw_config"].full_scan_threshold == 500


# ─── Full-Text Payload Index Tests ──────────────────────────────────


async def test_ensure_collection_creates_payload_index(
    store: QdrantVectorStore,
    mock_qdrant_client: AsyncMock,
) -> None:
    """Collection init should create a payload index on 'name' field."""
    mock_qdrant_client.get_collections.return_value.collections = []
    await store._ensure_collection()
    mock_qdrant_client.create_payload_index.assert_awaited()
    # Verify it's for the 'name' field
    call_kwargs = mock_qdrant_client.create_payload_index.call_args[1]
    assert call_kwargs["field_name"] == "name"


# ─── _cosine_similarity Tests ───────────────────────────────────────


def test_cosine_similarity_non_list_input() -> None:
    """Non-list inputs return 0.0 (guard clause coverage)."""
    result = QdrantVectorStore._cosine_similarity("not a list", [1.0, 2.0])
    assert result == 0.0
    result2 = QdrantVectorStore._cosine_similarity([1.0, 2.0], None)
    assert result2 == 0.0
