"""Abstract protocols for dependency injection (embedding, storage, etc.)."""

from typing import Protocol, runtime_checkable


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
