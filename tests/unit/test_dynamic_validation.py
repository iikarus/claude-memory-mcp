"""Tests for dynamic ontology-based type validation in entity creation.

Phase 0 fix: patched MemoryRepository/LockManager/QdrantVectorStore/ActivationEngine
to prevent live connection attempts during unit tests.
"""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from claude_memory.ontology import OntologyManager
from claude_memory.schema import EntityCreateParams


@pytest.fixture
def clean_ontology_file() -> Generator[str, None, None]:
    filename = "test_dynamic_ontology.json"
    if os.path.exists(filename):
        os.remove(filename)
    yield filename
    if os.path.exists(filename):
        os.remove(filename)


@pytest.fixture
def service_with_ontology(clean_ontology_file: str) -> Generator[Any, None, None]:
    """Create a MemoryService with real OntologyManager but mocked infrastructure."""
    repo_mock = MagicMock()
    repo_mock.create_node.return_value = {
        "id": "123",
        "name": "Test",
        "node_type": "Entity",
        "project_id": "p1",
    }
    repo_mock.get_total_node_count.return_value = 1
    repo_mock.get_most_recent_entity.return_value = None

    embedder_mock = MagicMock()
    embedder_mock.encode.return_value = [0.1] * 1024

    vector_mock = MagicMock()
    vector_mock.upsert = AsyncMock()

    # Real ontology with temp file — reset to only have Entity + Concept
    real_ontology = OntologyManager(config_path=clean_ontology_file)

    # Async context manager mock for lock
    lock_ctx = AsyncMock()
    lock_ctx.__aenter__ = AsyncMock(return_value=lock_ctx)
    lock_ctx.__aexit__ = AsyncMock(return_value=False)

    lock_manager_mock = MagicMock()
    lock_manager_mock.lock.return_value = lock_ctx

    with (
        patch("claude_memory.tools.MemoryRepository", return_value=repo_mock),
        patch("claude_memory.tools.LockManager", return_value=lock_manager_mock),
        patch("claude_memory.tools.QdrantVectorStore", return_value=vector_mock),
        patch("claude_memory.tools.OntologyManager", return_value=real_ontology),
        patch("claude_memory.tools.ActivationEngine"),
    ):
        from claude_memory.tools import MemoryService

        service = MemoryService(embedding_service=embedder_mock)
        yield service


# ── Evil Tests ──────────────────────────────────────────────────────


async def test_create_entity_evil_invalid_type_rejected(
    service_with_ontology: Any,
) -> None:
    """Evil: creating with an invalid type must raise ValueError."""
    params = EntityCreateParams(name="Test", node_type="InvalidType", project_id="p1")
    with pytest.raises(ValueError, match="Invalid memory type"):
        await service_with_ontology.create_entity(params)


async def test_create_entity_evil_empty_type_rejected(
    service_with_ontology: Any,
) -> None:
    """Evil: empty string type must raise ValueError."""
    params = EntityCreateParams(name="Test", node_type="", project_id="p1")
    with pytest.raises(ValueError, match="Invalid memory type"):
        await service_with_ontology.create_entity(params)


async def test_create_entity_evil_case_sensitive_type(
    service_with_ontology: Any,
) -> None:
    """Evil: type names are case-sensitive — 'entity' != 'Entity'."""
    params = EntityCreateParams(name="Test", node_type="entity", project_id="p1")
    with pytest.raises(ValueError, match="Invalid memory type"):
        await service_with_ontology.create_entity(params)


# ── Sad Test ────────────────────────────────────────────────────────


async def test_create_entity_sad_unregistered_custom_type(
    service_with_ontology: Any,
) -> None:
    """Sad: attempting to use a type that was never registered."""
    params = EntityCreateParams(name="Soup", node_type="Recipe", project_id="p1")
    with pytest.raises(ValueError, match="Invalid memory type"):
        await service_with_ontology.create_entity(params)


# ── Happy Tests ─────────────────────────────────────────────────────


async def test_create_entity_happy_default_type(
    service_with_ontology: Any,
) -> None:
    """Happy: creating with a default ontology type succeeds."""
    params = EntityCreateParams(name="Test", node_type="Entity", project_id="p1")
    receipt = await service_with_ontology.create_entity(params)
    assert receipt.id == "123"
    assert receipt.status == "committed"
    service_with_ontology.repo.create_node.assert_called_with("Entity", ANY)


async def test_create_entity_happy_dynamic_type(
    service_with_ontology: Any,
) -> None:
    """Happy: registering a new type then creating an entity of that type."""
    service_with_ontology.create_memory_type("Recipe", "Cooking recipes", [])
    params = EntityCreateParams(name="Soup", node_type="Recipe", project_id="p1")
    receipt = await service_with_ontology.create_entity(params)
    assert receipt.id == "123"
    service_with_ontology.repo.create_node.assert_called_with("Recipe", ANY)
