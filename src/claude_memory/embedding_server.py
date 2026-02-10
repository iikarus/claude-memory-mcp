"""FastAPI microservice exposing the EmbeddingService as an HTTP endpoint."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import the existing service logic so we reuse the model loading code
from claude_memory.embedding import EmbeddingService
from claude_memory.logging_config import configure_logging

# Configure logging
configure_logging()
logger = logging.getLogger("embedding-server")

# Global instance
service: EmbeddingService | None = None


class EmbedRequest(BaseModel):
    """Request payload containing texts to embed."""

    texts: list[str]


class EmbedResponse(BaseModel):
    """Response payload containing computed embedding vectors."""

    embeddings: list[list[float]]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the global EmbeddingService and pre-load the model."""
    global service  # noqa: PLW0603
    logger.info("Initializing Embedding Service...")
    service = EmbeddingService()
    # Trigger model load
    _ = service.encoder
    logger.info(f"Model loaded on {service.device}")
    yield


app = FastAPI(title="Embedding Service", lifespan=lifespan)


@app.post("/embed", response_model=EmbedResponse)  # type: ignore[misc, unused-ignore]
async def embed_texts(request: EmbedRequest) -> dict[str, Any]:
    """Encode input texts and return their embedding vectors."""
    if not request.texts:
        return {"embeddings": []}

    if service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        embeddings = service.encode_batch(request.texts)
        return {"embeddings": embeddings}
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")  # type: ignore[misc, unused-ignore]
async def health() -> dict[str, str]:
    """Health check endpoint returning service status and device info."""
    device = service.device if service else "unknown"
    return {"status": "ok", "device": device}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
