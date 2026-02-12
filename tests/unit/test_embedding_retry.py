"""Tests for embedding CUDA context retry (R-4).

Validates that EmbeddingService.encode() and encode_batch() retry once
on RuntimeError by clearing the encoder cache and reloading the model.
"""

from unittest.mock import MagicMock, PropertyMock, patch

from claude_memory.embedding import EmbeddingService


def _make_service() -> EmbeddingService:
    """Create an EmbeddingService without triggering local model load."""
    svc = EmbeddingService.__new__(EmbeddingService)
    svc.model_name = "test-model"
    svc._encoder = None
    svc._device = None
    return svc


class TestEncodeRetry:
    """encode() retries once on RuntimeError then succeeds or propagates."""

    @patch.dict("os.environ", {}, clear=True)
    def test_encode_retries_on_runtime_error(self) -> None:
        """First call raises RuntimeError; retry succeeds after encoder reload."""
        svc = _make_service()

        fake_vec = MagicMock()
        fake_vec.tolist.return_value = [1.0, 2.0, 3.0]

        mock_encoder = MagicMock()
        mock_encoder.encode.side_effect = [RuntimeError("CUDA context lost"), fake_vec]

        with patch.object(
            EmbeddingService, "encoder", new_callable=PropertyMock, return_value=mock_encoder
        ):
            result = svc.encode("hello")

        assert result == [1.0, 2.0, 3.0]
        assert mock_encoder.encode.call_count == 2

    @patch.dict("os.environ", {}, clear=True)
    def test_encode_propagates_on_double_failure(self) -> None:
        """If both first call and retry raise, the exception propagates."""
        svc = _make_service()

        mock_encoder = MagicMock()
        mock_encoder.encode.side_effect = RuntimeError("CUDA unrecoverable")

        with patch.object(
            EmbeddingService, "encoder", new_callable=PropertyMock, return_value=mock_encoder
        ):
            try:
                svc.encode("hello")
                assert False, "Should have raised RuntimeError"  # noqa: B011
            except RuntimeError:
                pass

        assert mock_encoder.encode.call_count == 2


class TestEncodeBatchRetry:
    """encode_batch() retries once on RuntimeError then succeeds or propagates."""

    @patch.dict("os.environ", {}, clear=True)
    def test_encode_batch_retries_on_runtime_error(self) -> None:
        """First call raises RuntimeError; retry succeeds after encoder reload."""
        svc = _make_service()

        fake_vecs = MagicMock()
        fake_vecs.tolist.return_value = [[1.0], [2.0]]

        mock_encoder = MagicMock()
        mock_encoder.encode.side_effect = [RuntimeError("CUDA context lost"), fake_vecs]

        with patch.object(
            EmbeddingService, "encoder", new_callable=PropertyMock, return_value=mock_encoder
        ):
            result = svc.encode_batch(["a", "b"])

        assert result == [[1.0], [2.0]]
        assert mock_encoder.encode.call_count == 2

    @patch.dict("os.environ", {}, clear=True)
    def test_encode_batch_empty_skips_encoder(self) -> None:
        """Empty input returns [] without touching the encoder."""
        svc = _make_service()
        result = svc.encode_batch([])
        assert result == []
