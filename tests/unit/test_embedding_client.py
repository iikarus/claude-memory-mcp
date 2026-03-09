import os
from unittest.mock import patch

import pytest

from claude_memory.embedding import EmbeddingService


class TestEmbeddingClient:
    @patch.dict(os.environ, {"EMBEDDING_API_URL": "http://mock-api"})
    def test_init_remote(self):
        """Test that init doesn't load model if API URL is set"""
        service = EmbeddingService()
        # Should NOT load encoder yet
        assert service._encoder is None

        # Accessing encoder property should raise error
        with pytest.raises(RuntimeError):
            _ = service.encoder

    @patch.dict(os.environ, {"EMBEDDING_API_URL": "http://mock-api"})
    @patch("claude_memory.embedding.httpx.Client")
    def test_encode_remote(self, mock_client_cls):
        """Test that encode calls the API"""
        service = EmbeddingService()

        # Mock Response
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_client.post.return_value.status_code = 200

        vec = service.encode("hello")

        assert vec == [0.1, 0.2, 0.3]
        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["texts"] == ["hello"]
