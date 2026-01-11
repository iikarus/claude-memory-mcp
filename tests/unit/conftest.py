from unittest.mock import AsyncMock

import pytest


# Define Mock Protocol or just a class
class MockVectorStore:
    def __init__(self) -> None:
        self.upsert = AsyncMock()
        self.search = AsyncMock(return_value=[])
        self.delete = AsyncMock()


@pytest.fixture
def mock_vector_store() -> MockVectorStore:
    return MockVectorStore()
