import logging
from typing import Any, Dict, List, Optional, Protocol

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)


class VectorStore(Protocol):
    """Protocol for vector storage operations."""

    async def upsert(self, id: str, vector: List[float], payload: Dict[str, Any]) -> None:
        """Insert or update a vector with payload."""
        ...

    async def search(
        self, vector: List[float], limit: int = 5, filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for nearest neighbors."""
        ...

    async def delete(self, id: str) -> None:
        """Delete a vector by ID."""
        ...


class QdrantVectorStore:
    """Qdrant implementation of VectorStore."""

    def __init__(
        self,
        host: str = "qdrant",
        port: int = 6333,
        collection: str = "memory_embeddings",
        vector_size: int = 1024,
    ):
        self.client = AsyncQdrantClient(host=host, port=port)
        self.collection = collection
        self.vector_size = vector_size
        self._initialized = False

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
                )
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant collection: {e}")
            # Don't raise, might be connection error handled later

    async def upsert(self, id: str, vector: List[float], payload: Dict[str, Any]) -> None:
        await self._ensure_collection()
        point = models.PointStruct(
            id=id, vector=vector, payload=payload  # Qdrant supports UUID strings
        )
        await self.client.upsert(collection_name=self.collection, points=[point])

    async def search(
        self, vector: List[float], limit: int = 5, filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        await self._ensure_collection()

        # Build Qdrant Filter
        q_filter = None
        if filter:
            must_conditions = []
            for k, v in filter.items():
                if k == "created_at_lt":
                    # Range filter for time
                    must_conditions.append(
                        models.FieldCondition(key="created_at", range=models.Range(lt=v))
                    )
                # Add other filter types here if needed (e.g. project_id)
                elif isinstance(v, (str, int, float, bool)):
                    must_conditions.append(
                        models.FieldCondition(key=k, match=models.MatchValue(value=v))
                    )

            if must_conditions:
                q_filter = models.Filter(must=must_conditions)

        # Search in Qdrant
        # Note: qdrant-client 1.7+ has search, but mypy might not see it correctly on Async client dynamic proxy
        results = await self.client.search(
            collection_name=self.collection, query_vector=vector, limit=limit, query_filter=q_filter
        )

        # Transform back to Dict
        output = []
        for hit in results:
            item = hit.payload or {}
            item["_id"] = hit.id
            item["_score"] = hit.score
            output.append(item)
        return output

    async def delete(self, id: str) -> None:
        await self._ensure_collection()
        await self.client.delete(
            collection_name=self.collection, points_selector=models.PointIdsList(points=[id])
        )
