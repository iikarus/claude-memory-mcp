import logging
import os
from typing import List, Optional, cast

import httpx
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles text embedding using SentenceTransformers.
    Encapsulates model loading and GPU management.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self._encoder: Optional[SentenceTransformer] = None
        self._device: Optional[str] = None

    @property
    def device(self) -> str:
        """Lazy load device detection."""
        if self._device is None:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        return self._device

    @property
    def encoder(self) -> SentenceTransformer:
        """Lazy load the encoder model."""
        # If API URL is set, we don't need the local model
        if os.getenv("EMBEDDING_API_URL"):
            raise RuntimeError("Should not access local encoder when using Remote API")

        if self._encoder is None:
            logger.info(
                f"Loading SentenceTransformer model ({self.model_name}) on {self.device}..."
            )
            self._encoder = SentenceTransformer(self.model_name, device=self.device)
        return self._encoder

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Helper to call remote embedding API."""
        url = os.getenv("EMBEDDING_API_URL")
        try:
            # We use a synchronous helper for compatibility with existing sync methods
            # ideally this class should be async but that requires refactoring MemoryService
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{url}/embed", json={"texts": texts})
                resp.raise_for_status()
                return cast(List[List[float]], resp.json()["embeddings"])
        except Exception as e:
            logger.error(f"Remote embedding failed: {e}")
            # Fallback? No, if configured for remote, failure should be noisy.
            raise e

    def encode(self, text: str) -> List[float]:
        """Encodes a single string into a vector."""
        if os.getenv("EMBEDDING_API_URL"):
            return self._call_api([text])[0]

        vec = self.encoder.encode(text)
        return cast(List[float], vec.tolist())

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encodes a list of strings."""
        if not texts:
            return []

        if os.getenv("EMBEDDING_API_URL"):
            return self._call_api(texts)

        vecs = self.encoder.encode(texts)
        return cast(List[List[float]], vecs.tolist())
