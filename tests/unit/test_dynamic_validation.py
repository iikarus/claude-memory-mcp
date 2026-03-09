import os
from collections.abc import Generator
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from claude_memory.ontology import OntologyManager
from claude_memory.schema import EntityCreateParams
from claude_memory.tools import MemoryService


@pytest.fixture
def memory_service() -> None:
    with (
        patch("claude_memory.repository.FalkorDB"),
        patch("claude_memory.embedding.EmbeddingService") as _,
        patch("claude_memory.ontology.OntologyManager") as _,
    ):
        pass

    # Let's use real OntologyManager for logic test, but mockup persistence?
    # Or just use the service fixture pattern
    pass


@pytest.fixture
def service_with_ontology() -> Generator[Any, None, None]:
    # Mock dependencies
    repo_mock = MagicMock()
    repo_mock.create_node.return_value = {"id": "123"}
    repo_mock.get_total_node_count.return_value = 1

    embedder_mock = MagicMock()
    embedder_mock.encode.return_value = [0.1] * 1024

    vector_mock = MagicMock()
    vector_mock.upsert = AsyncMock()

    # Use real ontology but with temp file
    # We can patch the init of OntologyManager in tools.py, OR inject it if refactored.
    # tools.py instantiates OntologyManager() inside __init__.
    # We should patch 'claude_memory.tools.OntologyManager' to return a controlled instance

    real_ontology = OntologyManager(config_path="test_dynamic_ontology.json")
    # Reset for test
    real_ontology._ontology = {"Entity": {}, "Concept": {}}

    with patch("claude_memory.ontology.OntologyManager", return_value=real_ontology):
        service = MemoryService(embedding_service=embedder_mock, vector_store=vector_mock)
        service.repo = repo_mock
    yield service

    if os.path.exists("test_dynamic_ontology.json"):
        os.remove("test_dynamic_ontology.json")


@pytest.mark.asyncio
async def test_create_entity_invalid_type_rejection(service_with_ontology: Any) -> None:
    params = EntityCreateParams(name="Test", node_type="InvalidType", project_id="p1")

    with pytest.raises(ValueError, match="Invalid memory type"):
        await service_with_ontology.create_entity(params)


@pytest.mark.asyncio
async def test_create_entity_valid_dynamic_type(service_with_ontology: Any) -> None:
    # 1. Register new type
    service_with_ontology.create_memory_type("Recipe", "Cooking", [])

    # 2. Create entity
    params = EntityCreateParams(name="Soup", node_type="Recipe", project_id="p1")
    receipt = await service_with_ontology.create_entity(params)

    assert receipt.id == "123"
    # Verify repo called with "Recipe"
    service_with_ontology.repo.create_node.assert_called_with("Recipe", ANY)
