import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import the existing service logic so we reuse the model loading code
from claude_memory.embedding import EmbeddingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedding-server")

app = FastAPI(title="Embedding Service")

# Global instance
service: Optional[EmbeddingService] = None


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]


@app.on_event("startup")  # type: ignore[misc, unused-ignore]
async def startup_event() -> None:
    global service
    logger.info("Initializing Embedding Service...")
    # Force GPU usage if available by initializing explicitly
    service = EmbeddingService()
    # Trigger model load
    _ = service.encoder
    logger.info(f"Model loaded on {service.device}")


@app.post("/embed", response_model=EmbedResponse)  # type: ignore[misc, unused-ignore]
async def embed_texts(request: EmbedRequest) -> Dict[str, Any]:
    if not request.texts:
        return {"embeddings": []}

    if service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        embeddings = service.encode_batch(request.texts)
        return {"embeddings": embeddings}
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")  # type: ignore[misc, unused-ignore]
async def health() -> Dict[str, str]:
    device = service.device if service else "unknown"
    return {"status": "ok", "device": device}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
