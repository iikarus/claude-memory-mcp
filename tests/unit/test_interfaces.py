import pytest
from claude_memory.interfaces import Embedder
from claude_memory.embedding import EmbeddingService
from unittest.mock import MagicMock

def test_embedding_service_implementation():
    """Verify EmbeddingService implements Embedder protocol (via structural subtyping check)."""
    # Note: Because @runtime_checkable is used, isinstance check works for Protocols
    # However, for pure structural typing without inheritance, Protocol checking at runtime inspects methods.
    
    # We construct it lazily/mocked to avoid full init if possible, but here we want to test the class structure.
    # Given torch loading is heavy, maybe just inspect the class methods? 
    # Or rely on Mypy. But let's instantiate.
    
    service = EmbeddingService(model_name="test-mock")
    # Mock the internal encoder to avoid real model load if lazy prop is accessed
    service._encoder = MagicMock()
    
    assert isinstance(service, Embedder)

def test_mock_implementation():
    """Verify a mock can satisfy the protocol."""
    class MockEmbedder:
        def encode(self, text: str) -> list[float]:
            return [0.1, 0.2]
            
    mock = MockEmbedder()
    assert isinstance(mock, Embedder)
