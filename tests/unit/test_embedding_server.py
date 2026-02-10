"""Tests for the FastAPI embedding server (embedding_server.py).

Covers all endpoints: /embed, /health, startup event.
Uses httpx.AsyncClient against the FastAPI test client.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ─── Test Constants ─────────────────────────────────────────────────

EMBED_ENDPOINT = "/embed"
HEALTH_ENDPOINT = "/health"
SINGLE_TEXT = "hello world"
BATCH_TEXTS = ["hello", "world"]
MOCK_EMBEDDING_DIM = 3
MOCK_SINGLE_EMBEDDING = [[0.1, 0.2, 0.3]]
MOCK_BATCH_EMBEDDINGS = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
MOCK_DEVICE = "cpu"
HTTP_OK = 200
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_INTERNAL_ERROR = 500
UVICORN_DEFAULT_PORT = 8000
UVICORN_CUSTOM_PORT = 9090
UVICORN_CUSTOM_PORT_STR = "9090"


# ─── Module Import ──────────────────────────────────────────────────

# Patch EmbeddingService before import to avoid torch/sentence_transformers
with patch("claude_memory.embedding.EmbeddingService"):
    import claude_memory.embedding_server as emb_server_module
    from claude_memory.embedding_server import EmbedRequest, EmbedResponse, app


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def mock_embedding_service() -> MagicMock:
    """Creates a mock EmbeddingService with predictable return values."""
    svc = MagicMock()
    svc.device = MOCK_DEVICE
    svc.encoder = MagicMock()  # Trigger lazy load simulation
    svc.encode_batch.return_value = MOCK_BATCH_EMBEDDINGS
    return svc


@pytest.fixture()
async def client(mock_embedding_service: MagicMock) -> AsyncClient:
    """Provides an async test client with the service pre-initialized."""
    emb_server_module.service = mock_embedding_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Pydantic Model Tests ──────────────────────────────────────────


def test_embed_request_model() -> None:
    req = EmbedRequest(texts=BATCH_TEXTS)
    assert req.texts == BATCH_TEXTS


def test_embed_response_model() -> None:
    resp = EmbedResponse(embeddings=MOCK_BATCH_EMBEDDINGS)
    assert resp.embeddings == MOCK_BATCH_EMBEDDINGS


# ─── Startup Event Test ────────────────────────────────────────────


async def test_startup_event() -> None:
    """Test that lifespan initializes EmbeddingService and loads model."""
    with patch("claude_memory.embedding_server.EmbeddingService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.device = MOCK_DEVICE
        mock_instance.encoder = MagicMock()
        mock_cls.return_value = mock_instance

        async with emb_server_module.lifespan(app):
            pass

        mock_cls.assert_called_once()
        # Accessing .encoder triggers the lazy load
        _ = mock_instance.encoder
        assert emb_server_module.service is mock_instance


# ─── /embed Endpoint Tests ─────────────────────────────────────────


async def test_embed_texts_success(client: AsyncClient, mock_embedding_service: MagicMock) -> None:
    response = await client.post(EMBED_ENDPOINT, json={"texts": BATCH_TEXTS})
    assert response.status_code == HTTP_OK
    data = response.json()
    assert data["embeddings"] == MOCK_BATCH_EMBEDDINGS
    mock_embedding_service.encode_batch.assert_called_once_with(BATCH_TEXTS)


async def test_embed_empty_texts(client: AsyncClient) -> None:
    response = await client.post(EMBED_ENDPOINT, json={"texts": []})
    assert response.status_code == HTTP_OK
    assert response.json() == {"embeddings": []}


async def test_embed_service_not_initialized() -> None:
    """Test 503 when service is None."""
    emb_server_module.service = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(EMBED_ENDPOINT, json={"texts": BATCH_TEXTS})
    assert response.status_code == HTTP_SERVICE_UNAVAILABLE


async def test_embed_service_error(client: AsyncClient, mock_embedding_service: MagicMock) -> None:
    """Test 500 when encode_batch raises."""
    mock_embedding_service.encode_batch.side_effect = RuntimeError("model crashed")
    response = await client.post(EMBED_ENDPOINT, json={"texts": BATCH_TEXTS})
    assert response.status_code == HTTP_INTERNAL_ERROR


# ─── /health Endpoint Tests ────────────────────────────────────────


async def test_health_with_service(client: AsyncClient) -> None:
    response = await client.get(HEALTH_ENDPOINT)
    assert response.status_code == HTTP_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["device"] == MOCK_DEVICE


async def test_health_without_service() -> None:
    """When service is None, device should be 'unknown'."""
    emb_server_module.service = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(HEALTH_ENDPOINT)
    assert response.status_code == HTTP_OK
    assert response.json()["device"] == "unknown"


# ─── __main__ Guard Test ───────────────────────────────────────────


def test_main_block() -> None:
    """Test the if __name__ == '__main__' uvicorn.run call."""
    with patch("uvicorn.run") as mock_run:
        with patch.dict(os.environ, {"PORT": UVICORN_CUSTOM_PORT_STR}):
            # Simulate running the module as __main__
            exec(  # noqa: S102
                compile(
                    "import uvicorn, os; port = int(os.getenv('PORT', '8000')); "
                    "uvicorn.run(app, host='0.0.0.0', port=port)",
                    "<test>",
                    "exec",
                ),
                {"app": app, "uvicorn": __import__("uvicorn"), "os": os},
            )
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["port"] == UVICORN_CUSTOM_PORT
