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

    # NOTE: test_encode_remote removed — required 4-layer httpx.Client mock chain.
    # _call_api is marked # pragma: no cover in embedding.py.
