"""Abstract protocols for dependency injection (embedding, storage, etc.)."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """
    Protocol for text embedding services.
    Allows swapping the concrete EmbeddingService (Torch/BGE-M3) with other implementations
    (API, Mock, etc).
    """

    def encode(self, text: str) -> list[float]:
        """Encodes a single string into a vector."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector storage operations."""

    async def upsert(self, id: str, vector: list[float], payload: dict[str, Any]) -> None:
        """Insert or update a vector with payload."""
        ...

    async def search(
        self,
        vector: list[float],
        limit: int = 5,
        filter: dict[str, Any] | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search for nearest neighbors."""
        ...

    async def search_mmr(
        self,
        vector: list[float],
        limit: int = 5,
        filter: dict[str, Any] | None = None,
        mmr_lambda: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search with Maximal Marginal Relevance for diversity."""
        ...

    async def delete(self, id: str) -> None:
        """Delete a vector by ID."""
        ...
