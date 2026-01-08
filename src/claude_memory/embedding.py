import logging
from typing import List, Optional, cast

import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles text embedding using SentenceTransformers.
    Encapsulates model loading and GPU management.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
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
        if self._encoder is None:
            logger.info(
                f"Loading SentenceTransformer model ({self.model_name}) on {self.device}..."
            )
            self._encoder = SentenceTransformer(self.model_name, device=self.device)
        return self._encoder

    def encode(self, text: str) -> List[float]:
        """Encodes a single string into a vector."""
        vec = self.encoder.encode(text)
        return cast(List[float], vec.tolist())

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encodes a list of strings."""
        vecs = self.encoder.encode(texts)
        return cast(List[List[float]], vecs.tolist())
