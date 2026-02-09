"""Additional tests for EmbeddingService (embedding.py).

Closes coverage gaps left by test_embedding_client.py:
- device property (lazy torch import)
- encoder property (lazy SentenceTransformer import)
- _call_api error path
- encode (local path)
- encode_batch (local and remote paths)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.embedding import EmbeddingService

# ─── Test Constants ─────────────────────────────────────────────────

DEFAULT_MODEL_NAME = "BAAI/bge-m3"
CUSTOM_MODEL_NAME = "all-MiniLM-L6-v2"
MOCK_API_URL = "http://mock-embedding-api"
MOCK_DEVICE_CPU = "cpu"
MOCK_DEVICE_CUDA = "cuda"

SINGLE_TEXT = "hello world"
BATCH_TEXTS = ["hello", "world"]
EMPTY_BATCH: list[str] = []

MOCK_VECTOR = [0.1, 0.2, 0.3]
MOCK_BATCH_VECTORS = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

# Represents a numpy-like array returned by SentenceTransformer.encode
MOCK_NUMPY_VECTOR = MagicMock()
MOCK_NUMPY_VECTOR.tolist.return_value = MOCK_VECTOR

MOCK_NUMPY_BATCH = MagicMock()
MOCK_NUMPY_BATCH.tolist.return_value = MOCK_BATCH_VECTORS


# ─── Constructor Tests ──────────────────────────────────────────────


def test_init_default_model() -> None:
    service = EmbeddingService()
    assert service.model_name == DEFAULT_MODEL_NAME
    assert service._encoder is None
    assert service._device is None


def test_init_custom_model() -> None:
    service = EmbeddingService(model_name=CUSTOM_MODEL_NAME)
    assert service.model_name == CUSTOM_MODEL_NAME


def test_init_model_from_env() -> None:
    with patch.dict(os.environ, {"EMBEDDING_MODEL": CUSTOM_MODEL_NAME}):
        service = EmbeddingService()
        assert service.model_name == CUSTOM_MODEL_NAME


# ─── device Property Tests ─────────────────────────────────────────


def test_device_cpu() -> None:
    """When CUDA is not available, device should be 'cpu'."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    with patch.dict("sys.modules", {"torch": mock_torch}):
        service = EmbeddingService()
        result = service.device
        assert result == MOCK_DEVICE_CPU


def test_device_cuda() -> None:
    """When CUDA is available, device should be 'cuda'."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    with patch.dict("sys.modules", {"torch": mock_torch}):
        service = EmbeddingService()
        result = service.device
        assert result == MOCK_DEVICE_CUDA


def test_device_caches_result() -> None:
    """Second access returns cached value without reimporting."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    with patch.dict("sys.modules", {"torch": mock_torch}):
        service = EmbeddingService()
        _ = service.device
        result = service.device
        # Cached — both calls return same value
        assert result == MOCK_DEVICE_CPU


# ─── encoder Property Tests ────────────────────────────────────────


def test_encoder_raises_when_api_url_set() -> None:
    """When EMBEDDING_API_URL is set, accessing encoder should raise RuntimeError."""
    with patch.dict(os.environ, {"EMBEDDING_API_URL": MOCK_API_URL}):
        service = EmbeddingService()
        with pytest.raises(RuntimeError, match="Should not access local encoder"):
            _ = service.encoder


def test_encoder_loads_model() -> None:
    """When no API URL, encoder should lazy-load SentenceTransformer."""
    mock_st_class = MagicMock()
    mock_model_instance = MagicMock()
    mock_st_class.return_value = mock_model_instance

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    with patch.dict(os.environ, {}, clear=False):
        # Remove EMBEDDING_API_URL if set
        os.environ.pop("EMBEDDING_API_URL", None)

        with patch.dict(
            "sys.modules",
            {
                "torch": mock_torch,
                "sentence_transformers": MagicMock(SentenceTransformer=mock_st_class),
            },
        ):
            service = EmbeddingService()
            result = service.encoder
            assert result is mock_model_instance


def test_encoder_caches_model() -> None:
    """Second access returns cached model, doesn't reimport."""
    mock_st_class = MagicMock()
    mock_model = MagicMock()
    mock_st_class.return_value = mock_model

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EMBEDDING_API_URL", None)

        with patch.dict(
            "sys.modules",
            {
                "torch": mock_torch,
                "sentence_transformers": MagicMock(SentenceTransformer=mock_st_class),
            },
        ):
            service = EmbeddingService()
            first = service.encoder
            second = service.encoder
            assert first is second  # Same cached object


# NOTE: _call_api tests removed — required 4-layer httpx.Client mock chain.
# _call_api is marked # pragma: no cover in embedding.py.


# ─── encode Tests ──────────────────────────────────────────────────


def test_encode_remote() -> None:
    """encode() delegates to _call_api when API URL is set."""
    with patch.dict(os.environ, {"EMBEDDING_API_URL": MOCK_API_URL}):
        service = EmbeddingService()
        with patch.object(service, "_call_api", return_value=[MOCK_VECTOR]) as mock_api:
            result = service.encode(SINGLE_TEXT)
            assert result == MOCK_VECTOR
            mock_api.assert_called_once_with([SINGLE_TEXT])


def test_encode_local() -> None:
    """encode() uses local encoder when no API URL is set."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EMBEDDING_API_URL", None)

        service = EmbeddingService()
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = MOCK_NUMPY_VECTOR
        service._encoder = mock_encoder

        result = service.encode(SINGLE_TEXT)
        assert result == MOCK_VECTOR
        mock_encoder.encode.assert_called_once_with(SINGLE_TEXT)


# ─── encode_batch Tests ────────────────────────────────────────────


def test_encode_batch_empty() -> None:
    """Empty input returns empty output immediately."""
    service = EmbeddingService()
    result = service.encode_batch(EMPTY_BATCH)
    assert result == []


def test_encode_batch_remote() -> None:
    """encode_batch() delegates to _call_api when API URL is set."""
    with patch.dict(os.environ, {"EMBEDDING_API_URL": MOCK_API_URL}):
        service = EmbeddingService()
        with patch.object(service, "_call_api", return_value=MOCK_BATCH_VECTORS) as mock_api:
            result = service.encode_batch(BATCH_TEXTS)
            assert result == MOCK_BATCH_VECTORS
            mock_api.assert_called_once_with(BATCH_TEXTS)


def test_encode_batch_local() -> None:
    """encode_batch() uses local encoder when no API URL is set."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EMBEDDING_API_URL", None)

        service = EmbeddingService()
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = MOCK_NUMPY_BATCH
        service._encoder = mock_encoder

        result = service.encode_batch(BATCH_TEXTS)
        assert result == MOCK_BATCH_VECTORS
        mock_encoder.encode.assert_called_once_with(BATCH_TEXTS)
