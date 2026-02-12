"""Text embedding service using SentenceTransformers with optional remote API fallback."""

import logging
import os
from typing import Any, cast

import httpx

# NOTE: torch and sentence_transformers are intentionally NOT imported here.
# They are lazy-imported inside properties to prevent cascade failures in
# test environments where the full torch import chain can crash on Windows.
# See dependency_analysis.md for the full explanation.

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles text embedding using SentenceTransformers.
    Encapsulates model loading and GPU management.
    """

    def __init__(self, model_name: str | None = None):
        """Initialize with an optional model name, defaulting to BAAI/bge-m3."""
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self._encoder: Any = None
        self._device: str | None = None

    @property
    def device(self) -> str:
        """Lazy load device detection."""
        if self._device is None:
            import torch  # noqa: PLC0415

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        return self._device

    @property
    def encoder(self) -> Any:
        """Lazy load the encoder model."""
        # If API URL is set, we don't need the local model
        if os.getenv("EMBEDDING_API_URL"):
            raise RuntimeError("Should not access local encoder when using Remote API")

        if self._encoder is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            logger.info(
                f"Loading SentenceTransformer model ({self.model_name}) on {self.device}..."
            )
            self._encoder = SentenceTransformer(self.model_name, device=self.device)
        return self._encoder

    def _call_api(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        """Helper to call remote embedding API."""
        url = os.getenv("EMBEDDING_API_URL")
        try:
            # We use a synchronous helper for compatibility with existing sync methods
            # ideally this class should be async but that requires refactoring MemoryService
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{url}/embed", json={"texts": texts})
                resp.raise_for_status()
                return cast(list[list[float]], resp.json()["embeddings"])
        except Exception as e:
            logger.error(f"Remote embedding failed: {e}")
            # Fallback? No, if configured for remote, failure should be noisy.
            raise e

    def _reload_encoder(self) -> None:
        """Discard the cached encoder so the next access reloads the model."""
        logger.warning("Clearing encoder cache — model will be reloaded on next call")
        self._encoder = None
        self._device = None

    def encode(self, text: str) -> list[float]:
        """Encodes a single string into a vector.

        If the local encoder raises RuntimeError (e.g. CUDA context lost),
        the model is reloaded and the call is retried once.
        """
        if os.getenv("EMBEDDING_API_URL"):
            return self._call_api([text])[0]

        try:
            vec = self.encoder.encode(text)
        except RuntimeError:
            logger.error("encode() failed — reloading model and retrying once")
            self._reload_encoder()
            vec = self.encoder.encode(text)
        return cast(list[float], vec.tolist())

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encodes a list of strings.

        Retries once on RuntimeError (CUDA context recovery).
        """
        if not texts:
            return []

        if os.getenv("EMBEDDING_API_URL"):
            return self._call_api(texts)

        try:
            vecs = self.encoder.encode(texts)
        except RuntimeError:
            logger.error("encode_batch() failed — reloading model and retrying once")
            self._reload_encoder()
            vecs = self.encoder.encode(texts)
        return cast(list[list[float]], vecs.tolist())
