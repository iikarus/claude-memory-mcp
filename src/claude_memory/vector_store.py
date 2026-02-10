"""Vector storage abstraction with Qdrant implementation for semantic search."""

import logging
import os
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from claude_memory.interfaces import VectorStore
from claude_memory.retry import retry_on_transient

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = ["QdrantVectorStore", "VectorStore"]


# HNSW indexing threshold: build index at 500 points instead of the default 10K.
# At ~452 vectors the default would never build a real HNSW graph.
HNSW_INDEXING_THRESHOLD = 500


class QdrantVectorStore:
    """Qdrant implementation of VectorStore."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection: str = "memory_embeddings",
        vector_size: int = 1024,
    ):
        """Connect to Qdrant and configure the target collection."""
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.client = AsyncQdrantClient(host=self.host, port=self.port)
        self.collection = collection
        self.vector_size = vector_size
        self._initialized = False

    @retry_on_transient()
    async def _ensure_collection(self) -> None:
        """Create collection if not exists."""
        if self._initialized:
            return

        try:
            # Check if exists
            collections = await self.client.get_collections()
            exists = any(c.name == self.collection for c in collections.collections)

            if not exists:
                logger.info(
                    f"Creating Qdrant collection '{self.collection}' with size {self.vector_size}"
                )
                await self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=models.VectorParams(
                        size=self.vector_size, distance=models.Distance.COSINE
                    ),
                    hnsw_config=models.HnswConfigDiff(
                        full_scan_threshold=HNSW_INDEXING_THRESHOLD,
                    ),
                )
                # Create payload index on 'name' for full-text filtering
                await self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name="name",
                    field_schema=models.TextIndexParams(
                        type=models.TextIndexType.TEXT,
                        tokenizer=models.TokenizerType.WORD,
                        min_token_len=2,
                        max_token_len=20,
                    ),
                )
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant collection: {e}")
            raise

    @retry_on_transient()
    async def upsert(self, id: str, vector: list[float], payload: dict[str, Any]) -> None:
        """Insert or update a vector with its metadata payload."""
        await self._ensure_collection()
        point = models.PointStruct(
            id=id,
            vector=vector,
            payload=payload,  # Qdrant supports UUID strings
        )
        await self.client.upsert(collection_name=self.collection, points=[point])

    def _build_filter(self, filter: dict[str, Any] | None) -> models.Filter | None:
        """Convert a filter dict to a Qdrant Filter object."""
        if not filter:
            return None
        must_conditions = []
        for k, v in filter.items():
            if k == "created_at_lt":
                must_conditions.append(
                    models.FieldCondition(key="created_at", range=models.Range(lt=v))
                )
            elif isinstance(v, (str, int, float, bool)):
                must_conditions.append(
                    models.FieldCondition(key=k, match=models.MatchValue(value=v))  # type: ignore
                )
        if must_conditions:
            return models.Filter(must=must_conditions)  # type: ignore
        return None

    @retry_on_transient()
    async def search(
        self,
        vector: list[float],
        limit: int = 5,
        filter: dict[str, Any] | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search for nearest neighbors by cosine similarity."""
        await self._ensure_collection()

        q_filter = self._build_filter(filter)

        # Search using query_points (search was removed/deprecated)
        # We need to map 'query_vector' to 'query'
        results = await self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            offset=offset,
            query_filter=q_filter,
            with_payload=True,
            with_vectors=False,
        )

        # Results from query_points are ScoredPoint objects directly
        # AsyncQdrantClient.query_points returns QueryResponse, which has a 'points' attribute.
        return [
            {
                "_id": point.id,
                "_score": point.score,
                "payload": point.payload or {},
            }
            for point in results.points
        ]

    @retry_on_transient()
    async def search_mmr(
        self,
        vector: list[float],
        limit: int = 5,
        filter: dict[str, Any] | None = None,
        mmr_lambda: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search with Maximal Marginal Relevance for diverse results.

        Over-fetches 3x candidates, then greedily selects for diversity.
        mmr_lambda: 1.0 = pure similarity, 0.0 = pure diversity.
        """
        await self._ensure_collection()

        # Over-fetch 3x candidates for MMR re-ranking pool
        fetch_limit = limit * 3

        # Build Qdrant filter (reuse same logic as search)
        q_filter = self._build_filter(filter)

        results = await self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=fetch_limit,
            query_filter=q_filter,
            with_payload=True,
            with_vectors=True,  # Need vectors for diversity calculation
        )

        candidates = results.points
        if not candidates:
            return []

        # Greedy MMR selection
        selected: list[Any] = []
        remaining = list(candidates)

        # First pick: highest similarity
        remaining.sort(key=lambda p: p.score, reverse=True)
        selected.append(remaining.pop(0))

        while len(selected) < limit and remaining:
            best_score = -1.0
            best_idx = 0
            for i, candidate in enumerate(remaining):
                # Similarity to query
                sim_query = candidate.score
                # Max similarity to already-selected (diversity penalty)
                max_sim_selected = max(
                    self._cosine_similarity(candidate.vector, s.vector) for s in selected
                )
                # MMR score: balance relevance vs diversity
                mmr_score = mmr_lambda * sim_query - (1 - mmr_lambda) * max_sim_selected
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        return [
            {
                "_id": point.id,
                "_score": point.score,
                "payload": point.payload or {},
            }
            for point in selected
        ]

    @staticmethod
    def _cosine_similarity(vec_a: list[float] | Any, vec_b: list[float] | Any) -> float:
        """Compute cosine similarity between two vectors."""
        if not isinstance(vec_a, list) or not isinstance(vec_b, list):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        mag_a = sum(a * a for a in vec_a) ** 0.5
        mag_b = sum(b * b for b in vec_b) ** 0.5
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return float(dot / (mag_a * mag_b))

    @retry_on_transient()
    async def delete(self, id: str) -> None:
        """Delete a vector by its ID."""
        await self._ensure_collection()
        await self.client.delete(
            collection_name=self.collection, points_selector=models.PointIdsList(points=[id])
        )
