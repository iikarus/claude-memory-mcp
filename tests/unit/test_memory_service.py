"""Coverage gap tests for MemoryService (tools.py).

Targets all uncovered lines: create_relationship (with/without project lock),
update_entity, delete_entity (soft/hard with vector delete failures),
delete_relationship, add_observation (entity not found), end_session (not found),
record_breakthrough (with/without session), traverse_path (with path nodes,
without nodes attribute), point_in_time_query, search (with results),
analyze_graph (pagerank success/error, louvain success/error),
get_stale_entities, consolidate_memories (with/without edge creation errors),
create_memory_type.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Test Constants ─────────────────────────────────────────────────

PROJECT_ID = "project-alpha"
ENTITY_ID = "entity-001"
ENTITY_ID_2 = "entity-002"
ENTITY_ID_3 = "entity-003"
ENTITY_NAME = "Python"
ENTITY_TYPE = "Language"
RELATIONSHIP_TYPE = "RELATED_TO"
RELATIONSHIP_ID = "rel-001"
CONFIDENCE_DEFAULT = 1.0

OBSERVATION_CONTENT = "Observed a critical pattern"
EVIDENCE_LIST = ["source-a", "source-b"]
CERTAINTY_CONFIRMED = "confirmed"
DELETE_REASON = "deprecated"

SESSION_ID = "session-001"
SESSION_FOCUS = "architecture"
SESSION_SUMMARY = "Reviewed patterns"
SESSION_OUTCOMES = ["fixed-race-condition"]

BREAKTHROUGH_NAME = "eureka"
BREAKTHROUGH_MOMENT = "2024-06-15T14:30:00Z"
BREAKTHROUGH_ANALOGY = "water-flow"
BREAKTHROUGH_CONCEPT = "async-patterns"

SEARCH_QUERY = "async patterns"
SEARCH_LIMIT = 5
TIME_AS_OF = "2024-01-01T00:00:00Z"
STALE_DAYS = 30

MOCK_EMBEDDING = [0.1, 0.2, 0.3]
MOCK_NODE_PROPS = {"id": ENTITY_ID, "name": ENTITY_NAME, "project_id": PROJECT_ID}

CONSOLIDATION_SUMMARY = "Merged related concepts"
CONSOLIDATION_TRUNCATED_LEN = 20

PAGERANK_SCORE = 0.85
COMMUNITY_ID = 1
COMMUNITY_SIZE = 5
COMMUNITY_MEMBERS = ["A", "B", "C"]


# ─── Module Import ──────────────────────────────────────────────────

with patch("claude_memory.repository.FalkorDB"):
    with patch("claude_memory.lock_manager.redis.Redis"):
        with patch("claude_memory.vector_store.AsyncQdrantClient"):
            from claude_memory.schema import (
                BreakthroughParams,
                EntityDeleteParams,
                EntityUpdateParams,
                ObservationParams,
                RelationshipCreateParams,
                RelationshipDeleteParams,
                SessionEndParams,
            )
            from claude_memory.tools import MemoryService


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def service() -> MemoryService:
    """Creates a MemoryService with all dependencies mocked."""
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = MOCK_EMBEDDING

    with patch("claude_memory.repository.FalkorDB"):
        with patch("claude_memory.lock_manager.redis.Redis"):
            with patch("claude_memory.vector_store.AsyncQdrantClient"):
                svc = MemoryService(embedding_service=mock_embedder)

    # Replace repo, vector_store, lock_manager with mocks
    svc.repo = MagicMock()
    svc.vector_store = AsyncMock()
    svc.lock_manager = MagicMock()

    # Lock context manager mock — supports both sync and async with
    mock_lock = MagicMock()
    mock_lock.__enter__ = MagicMock(return_value=mock_lock)
    mock_lock.__exit__ = MagicMock(return_value=False)
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock(return_value=False)
    svc.lock_manager.lock.return_value = mock_lock

    return svc


def _make_cypher_result(rows: list[list[Any]]) -> MagicMock:
    """Creates a mock Cypher query result."""
    result = MagicMock()
    result.result_set = rows
    return result


# ─── create_relationship Tests ──────────────────────────────────────


async def test_create_relationship_with_project_lock(service: MemoryService) -> None:
    """When source node has project_id, use project lock."""
    service.repo.get_node.return_value = {"id": ENTITY_ID, "project_id": PROJECT_ID}
    service.repo.create_edge.return_value = {"id": RELATIONSHIP_ID}

    params = RelationshipCreateParams(
        from_entity=ENTITY_ID,
        to_entity=ENTITY_ID_2,
        relationship_type=RELATIONSHIP_TYPE,
    )
    result = await service.create_relationship(params)
    assert result["id"] == RELATIONSHIP_ID


async def test_create_relationship_without_project(service: MemoryService) -> None:
    """When source node has no project_id, proceed without lock."""
    service.repo.get_node.return_value = {"id": ENTITY_ID}
    service.repo.create_edge.return_value = {"id": RELATIONSHIP_ID}

    params = RelationshipCreateParams(
        from_entity=ENTITY_ID,
        to_entity=ENTITY_ID_2,
        relationship_type=RELATIONSHIP_TYPE,
    )
    result = await service.create_relationship(params)
    assert result["id"] == RELATIONSHIP_ID


async def test_create_relationship_source_not_found(service: MemoryService) -> None:
    """When source node doesn't exist."""
    service.repo.get_node.return_value = None
    service.repo.create_edge.return_value = {"id": RELATIONSHIP_ID}

    params = RelationshipCreateParams(
        from_entity=ENTITY_ID,
        to_entity=ENTITY_ID_2,
        relationship_type=RELATIONSHIP_TYPE,
    )
    result = await service.create_relationship(params)
    assert result["id"] == RELATIONSHIP_ID


async def test_create_relationship_with_existing_id_in_props(service: MemoryService) -> None:
    """Branch 157→16: 'id' already in properties, UUID generation skipped."""
    service.repo.get_node.return_value = None
    pre_set_id = "custom-rel-id-999"
    service.repo.create_edge.return_value = {"id": pre_set_id}

    params = RelationshipCreateParams(
        from_entity=ENTITY_ID,
        to_entity=ENTITY_ID_2,
        relationship_type=RELATIONSHIP_TYPE,
        properties={"id": pre_set_id},
    )
    result = await service.create_relationship(params)
    assert result["id"] == pre_set_id
    # Verify the id we passed was preserved (not overwritten by uuid)
    call_args = service.repo.create_edge.call_args
    assert call_args[0][3]["id"] == pre_set_id


async def test_create_relationship_edge_creation_fails(service: MemoryService) -> None:
    """When edge creation returns empty result."""
    service.repo.get_node.return_value = None
    service.repo.create_edge.return_value = {}

    params = RelationshipCreateParams(
        from_entity=ENTITY_ID,
        to_entity=ENTITY_ID_2,
        relationship_type=RELATIONSHIP_TYPE,
    )
    result = await service.create_relationship(params)
    assert "error" in result


# ─── update_entity Tests ───────────────────────────────────────────


async def test_update_entity_with_project_lock(service: MemoryService) -> None:
    service.repo.get_node.return_value = MOCK_NODE_PROPS
    service.repo.update_node.return_value = {**MOCK_NODE_PROPS, "version": "2.0"}

    params = EntityUpdateParams(entity_id=ENTITY_ID, properties={"version": "2.0"}, reason="update")
    result = await service.update_entity(params)
    assert result["version"] == "2.0"


async def test_update_entity_not_found(service: MemoryService) -> None:
    service.repo.get_node.return_value = None

    params = EntityUpdateParams(entity_id=ENTITY_ID, properties={"version": "2.0"}, reason="update")
    result = await service.update_entity(params)
    assert result == {"error": "Entity not found"}


# ─── delete_entity Tests ───────────────────────────────────────────


async def test_delete_entity_soft(service: MemoryService) -> None:
    service.repo.get_node.return_value = MOCK_NODE_PROPS

    params = EntityDeleteParams(entity_id=ENTITY_ID, reason=DELETE_REASON, soft_delete=True)
    result = await service.delete_entity(params)
    assert result["status"] == "archived"
    service.repo.update_node.assert_called_once()
    service.vector_store.delete.assert_awaited_once_with(ENTITY_ID)


async def test_delete_entity_soft_vector_delete_fails(service: MemoryService) -> None:
    """Soft delete should succeed even when vector store delete fails."""
    service.repo.get_node.return_value = MOCK_NODE_PROPS
    service.vector_store.delete.side_effect = ConnectionError("qdrant down")

    params = EntityDeleteParams(entity_id=ENTITY_ID, reason=DELETE_REASON, soft_delete=True)
    result = await service.delete_entity(params)
    assert result["status"] == "archived"


async def test_delete_entity_hard(service: MemoryService) -> None:
    service.repo.get_node.return_value = MOCK_NODE_PROPS

    params = EntityDeleteParams(entity_id=ENTITY_ID, reason=DELETE_REASON, soft_delete=False)
    result = await service.delete_entity(params)
    assert result["status"] == "deleted"
    service.repo.delete_node.assert_called_once_with(ENTITY_ID)


async def test_delete_entity_hard_vector_delete_fails(service: MemoryService) -> None:
    """Hard delete should succeed even when vector store delete fails."""
    service.repo.get_node.return_value = MOCK_NODE_PROPS
    service.vector_store.delete.side_effect = ConnectionError("qdrant down")

    params = EntityDeleteParams(entity_id=ENTITY_ID, reason=DELETE_REASON, soft_delete=False)
    result = await service.delete_entity(params)
    assert result["status"] == "deleted"


async def test_delete_entity_not_found(service: MemoryService) -> None:
    service.repo.get_node.return_value = None

    params = EntityDeleteParams(entity_id=ENTITY_ID, reason=DELETE_REASON, soft_delete=True)
    result = await service.delete_entity(params)
    assert result == {"error": "Entity not found"}


async def test_delete_entity_no_project(service: MemoryService) -> None:
    """Entity without project_id should still delete without lock."""
    service.repo.get_node.return_value = {"id": ENTITY_ID, "name": ENTITY_NAME}

    params = EntityDeleteParams(entity_id=ENTITY_ID, reason=DELETE_REASON, soft_delete=True)
    result = await service.delete_entity(params)
    assert result["status"] == "archived"


# ─── delete_relationship Tests ─────────────────────────────────────


async def test_delete_relationship(service: MemoryService) -> None:
    params = RelationshipDeleteParams(relationship_id=RELATIONSHIP_ID, reason=DELETE_REASON)
    result = await service.delete_relationship(params)
    assert result == {"status": "deleted", "id": RELATIONSHIP_ID}
    service.repo.delete_edge.assert_called_once_with(RELATIONSHIP_ID)


# ─── add_observation Tests ─────────────────────────────────────────


async def test_add_observation_success(service: MemoryService) -> None:
    mock_obs_node = MagicMock()
    mock_obs_node.properties = {"id": "obs-001", "content": OBSERVATION_CONTENT}
    service.repo.execute_cypher.return_value = _make_cypher_result([[mock_obs_node]])

    params = ObservationParams(
        entity_id=ENTITY_ID,
        content=OBSERVATION_CONTENT,
        certainty=CERTAINTY_CONFIRMED,
        evidence=EVIDENCE_LIST,
    )
    result = await service.add_observation(params)
    assert result["content"] == OBSERVATION_CONTENT


async def test_add_observation_entity_not_found(service: MemoryService) -> None:
    service.repo.execute_cypher.return_value = _make_cypher_result([])

    params = ObservationParams(
        entity_id=ENTITY_ID,
        content=OBSERVATION_CONTENT,
        certainty=CERTAINTY_CONFIRMED,
    )
    result = await service.add_observation(params)
    assert result == {"error": "Entity not found"}


# ─── end_session Tests ─────────────────────────────────────────────


async def test_end_session_not_found(service: MemoryService) -> None:
    service.repo.execute_cypher.return_value = _make_cypher_result([])

    params = SessionEndParams(
        session_id=SESSION_ID, summary=SESSION_SUMMARY, outcomes=SESSION_OUTCOMES
    )
    result = await service.end_session(params)
    assert result == {"error": "Session not found"}


# ─── record_breakthrough Tests ─────────────────────────────────────


async def test_record_breakthrough_with_session(service: MemoryService) -> None:
    service.repo.create_node.return_value = {"id": "b-001", "name": BREAKTHROUGH_NAME}

    params = BreakthroughParams(
        name=BREAKTHROUGH_NAME,
        moment=BREAKTHROUGH_MOMENT,
        session_id=SESSION_ID,
        analogy_used=BREAKTHROUGH_ANALOGY,
        concepts_unlocked=[BREAKTHROUGH_CONCEPT],
    )
    result = await service.record_breakthrough(params)
    assert result["name"] == BREAKTHROUGH_NAME
    # Verify edge was created linking session to breakthrough
    service.repo.create_edge.assert_called_once()


async def test_record_breakthrough_without_session(service: MemoryService) -> None:
    """When session_id is empty, no edge should be created."""
    service.repo.create_node.return_value = {"id": "b-001", "name": BREAKTHROUGH_NAME}

    params = BreakthroughParams(
        name=BREAKTHROUGH_NAME,
        moment=BREAKTHROUGH_MOMENT,
        session_id="",
    )
    result = await service.record_breakthrough(params)
    assert result["name"] == BREAKTHROUGH_NAME
    service.repo.create_edge.assert_not_called()


# ─── traverse_path Tests ──────────────────────────────────────────


async def test_traverse_path_with_nodes(service: MemoryService) -> None:
    """When path has .nodes attribute, extract properties."""
    mock_node_a = MagicMock()
    mock_node_a.properties = {"id": ENTITY_ID, "name": "NodeA", "embedding": MOCK_EMBEDDING}
    mock_node_b = MagicMock()
    mock_node_b.properties = {"id": ENTITY_ID_2, "name": "NodeB"}

    mock_path = MagicMock()
    mock_path.nodes = [mock_node_a, mock_node_b]

    service.repo.execute_cypher.return_value = _make_cypher_result([[mock_path]])

    result = await service.traverse_path(ENTITY_ID, ENTITY_ID_2)
    assert len(result) == 2
    # Verify embedding was stripped
    assert "embedding" not in result[0]


async def test_traverse_path_no_path_found(service: MemoryService) -> None:
    service.repo.execute_cypher.return_value = _make_cypher_result([])

    result = await service.traverse_path(ENTITY_ID, ENTITY_ID_2)
    assert result == []


async def test_traverse_path_no_nodes_attr(service: MemoryService) -> None:
    """When path object doesn't have .nodes attribute."""
    mock_path = MagicMock(spec=[])  # No attributes
    service.repo.execute_cypher.return_value = _make_cypher_result([[mock_path]])

    result = await service.traverse_path(ENTITY_ID, ENTITY_ID_2)
    assert result == []


# ─── search Tests ──────────────────────────────────────────────────


async def test_search_empty_query(service: MemoryService) -> None:
    result = await service.search("", limit=SEARCH_LIMIT)
    assert result == []


async def test_search_no_vector_results(service: MemoryService) -> None:
    service.vector_store.search.return_value = []

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT)
    assert result == []


async def test_search_with_results(service: MemoryService) -> None:
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "project_id": PROJECT_ID,
                "description": "A programming language",
            }
        ],
        "edges": [],
    }

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT)
    assert len(result) == 1
    assert result[0].id == ENTITY_ID
    assert result[0].name == ENTITY_NAME
    assert result[0].score == PAGERANK_SCORE


async def test_search_node_not_in_graph(service: MemoryService) -> None:
    """When vector result ID is not in graph, it's excluded."""
    service.vector_store.search.return_value = [
        {"_id": "orphan-id", "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {"nodes": [], "edges": []}

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT)
    assert result == []


# ─── search with project_id filter ─────────────────────────────────


async def test_search_with_project_id_filter(service: MemoryService) -> None:
    """Search with project_id passes filter to vector store."""
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "project_id": PROJECT_ID,
                "description": "A language",
            }
        ],
        "edges": [],
    }

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT, project_id=PROJECT_ID)
    assert len(result) == 1

    # Verify filter was passed to vector_store.search
    call_kwargs = service.vector_store.search.call_args[1]
    assert call_kwargs["filter"] == {"project_id": PROJECT_ID}


async def test_search_with_mmr_flag(service: MemoryService) -> None:
    """When mmr=True, search delegates to vector_store.search_mmr."""
    service.vector_store.search_mmr.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "project_id": PROJECT_ID,
                "description": "A language",
            }
        ],
        "edges": [],
    }

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT, mmr=True)
    assert len(result) == 1
    # Verify search_mmr was called instead of search
    service.vector_store.search_mmr.assert_awaited_once()
    service.vector_store.search.assert_not_awaited()


# ─── point_in_time_query Tests ─────────────────────────────────────


async def test_point_in_time_query_no_results(service: MemoryService) -> None:
    service.vector_store.search.return_value = []

    result = await service.point_in_time_query(SEARCH_QUERY, TIME_AS_OF)
    assert result == []


async def test_point_in_time_query_with_results(service: MemoryService) -> None:
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [{"id": ENTITY_ID, "name": ENTITY_NAME}],
        "edges": [],
    }

    result = await service.point_in_time_query(SEARCH_QUERY, TIME_AS_OF)
    assert len(result) == 1
    assert result[0]["id"] == ENTITY_ID


# ─── analyze_graph Tests ──────────────────────────────────────────


async def test_analyze_graph_pagerank_success(service: MemoryService) -> None:
    mock_node = MagicMock()
    mock_node.properties = {"name": ENTITY_NAME, "rank": PAGERANK_SCORE}
    mock_node.labels = [ENTITY_TYPE, "Entity"]

    service.repo.execute_cypher.side_effect = [
        None,  # CALL algo.pageRank
        _make_cypher_result([[mock_node]]),  # MATCH RETURN
    ]

    result = await service.analyze_graph(algorithm="pagerank")
    assert len(result) == 1
    assert result[0]["name"] == ENTITY_NAME
    assert result[0]["rank"] == PAGERANK_SCORE


async def test_analyze_graph_pagerank_only_entity_label(service: MemoryService) -> None:
    """When node only has 'Entity' label, type should be 'Entity'."""
    mock_node = MagicMock()
    mock_node.properties = {"name": ENTITY_NAME, "rank": PAGERANK_SCORE}
    mock_node.labels = ["Entity"]  # Only Entity label

    service.repo.execute_cypher.side_effect = [
        None,
        _make_cypher_result([[mock_node]]),
    ]

    result = await service.analyze_graph(algorithm="pagerank")
    assert result[0]["type"] == "Entity"


async def test_analyze_graph_pagerank_error(service: MemoryService) -> None:
    service.repo.execute_cypher.side_effect = RuntimeError("algo not available")

    result = await service.analyze_graph(algorithm="pagerank")
    assert len(result) == 1
    assert "error" in result[0]


async def test_analyze_graph_louvain_success(service: MemoryService) -> None:
    service.repo.execute_cypher.side_effect = [
        None,  # CALL algo.louvain
        _make_cypher_result([[COMMUNITY_ID, COMMUNITY_SIZE, COMMUNITY_MEMBERS]]),
    ]

    result = await service.analyze_graph(algorithm="louvain")
    assert len(result) == 1
    assert result[0]["community_id"] == COMMUNITY_ID
    assert result[0]["size"] == COMMUNITY_SIZE


async def test_analyze_graph_louvain_error(service: MemoryService) -> None:
    service.repo.execute_cypher.side_effect = RuntimeError("algo not available")

    result = await service.analyze_graph(algorithm="louvain")
    assert len(result) == 1
    assert "error" in result[0]


async def test_analyze_graph_unsupported_algorithm(service: MemoryService) -> None:
    """Branch 587→601: algorithm is neither 'pagerank' nor 'louvain' → empty results."""
    result = await service.analyze_graph(algorithm="unknown")  # type: ignore[arg-type]
    assert result == []


# ─── get_stale_entities Tests ──────────────────────────────────────


async def test_get_stale_entities(service: MemoryService) -> None:
    mock_node = MagicMock()
    mock_node.properties = {"id": ENTITY_ID, "name": ENTITY_NAME, "embedding": MOCK_EMBEDDING}

    service.repo.execute_cypher.return_value = _make_cypher_result([[mock_node]])

    result = await service.get_stale_entities(days=STALE_DAYS)
    assert len(result) == 1
    assert result[0]["id"] == ENTITY_ID
    # Verify embedding was stripped
    assert "embedding" not in result[0]


# ─── consolidate_memories Tests ─────────────────────────────────────


async def test_consolidate_memories(service: MemoryService) -> None:
    service.repo.create_node.return_value = {"id": "consolidated-001", "name": "Consolidated"}

    result = await service.consolidate_memories(
        entity_ids=[ENTITY_ID, ENTITY_ID_2],
        summary=CONSOLIDATION_SUMMARY,
    )
    assert result["id"] == "consolidated-001"
    service.vector_store.upsert.assert_awaited_once()


async def test_consolidate_memories_edge_error(service: MemoryService) -> None:
    """When linking an old entity fails, continue with remaining."""
    service.repo.create_node.return_value = {"id": "consolidated-001", "name": "Consolidated"}
    service.repo.create_edge.side_effect = [
        RuntimeError("edge failed"),  # First entity fails
        MagicMock(),  # Second succeeds
    ]
    service.repo.update_node.return_value = {}

    result = await service.consolidate_memories(
        entity_ids=[ENTITY_ID, ENTITY_ID_2],
        summary=CONSOLIDATION_SUMMARY,
    )
    assert result["id"] == "consolidated-001"


# ─── create_memory_type Tests ──────────────────────────────────────


def test_create_memory_type(service: MemoryService) -> None:
    service.ontology = MagicMock()

    result = service.create_memory_type(
        name="Recipe",
        description="Culinary recipe",
        required_properties=["ingredients"],
    )
    assert result["name"] == "Recipe"
    assert result["status"] == "active"


def test_create_memory_type_defaults(service: MemoryService) -> None:
    service.ontology = MagicMock()

    result = service.create_memory_type(name="Recipe", description="Culinary recipe")
    assert result["required_properties"] == []


# ─── get_hologram Tests ────────────────────────────────────────────

HOLOGRAM_QUERY = "async patterns"
HOLOGRAM_DEPTH = 2
HOLOGRAM_MAX_TOKENS = 4000


async def test_get_hologram_no_anchors(service: MemoryService) -> None:
    """Line 715: search returns no anchors → early return."""
    service.vector_store.search.return_value = []

    result = await service.get_hologram(HOLOGRAM_QUERY, depth=HOLOGRAM_DEPTH)
    assert result == {"nodes": [], "edges": []}


async def test_get_hologram_with_non_dict_nodes(service: MemoryService) -> None:
    """Branch 733→732: raw_nodes contains a non-dict item → isinstance check False."""
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "embedding": MOCK_EMBEDDING,
            },
        ],
        "edges": [],
    }

    # Mock search properly — it calls get_subgraph internally
    mock_search_result = MagicMock()
    mock_search_result.id = ENTITY_ID
    mock_search_result.name = ENTITY_NAME
    mock_search_result.score = PAGERANK_SCORE
    mock_search_result.model_dump.return_value = {"id": ENTITY_ID, "name": ENTITY_NAME}

    # Hologram's internal search call returns results
    with patch.object(service, "search", return_value=[mock_search_result]):
        # get_subgraph returns both dict and non-dict nodes
        service.repo.get_subgraph.return_value = {
            "nodes": [
                {"id": ENTITY_ID, "name": ENTITY_NAME, "embedding": MOCK_EMBEDDING},
                MagicMock(),  # non-dict node → branch 733→732 False
            ],
            "edges": [],
        }
        service.context_manager = MagicMock()
        service.context_manager.optimize.return_value = [
            {"id": ENTITY_ID, "name": ENTITY_NAME},
        ]

        result = await service.get_hologram(
            HOLOGRAM_QUERY, depth=HOLOGRAM_DEPTH, max_tokens=HOLOGRAM_MAX_TOKENS
        )

    assert result["query"] == HOLOGRAM_QUERY
    assert len(result["nodes"]) == 1
    # Embedding should have been stripped from the dict node
    assert "embedding" not in result["nodes"][0]


# ─── Salience Scoring Tests ────────────────────────────────────────


SALIENCE_DEFAULT = 1.0
RETRIEVAL_COUNT_DEFAULT = 0
SALIENCE_AFTER_ONE_RETRIEVAL = 2.0  # 1.0 + log2(1 + 1) = 1.0 + 1.0


async def test_create_entity_initializes_salience(service: MemoryService) -> None:
    """create_entity sets salience_score=1.0 and retrieval_count=0 on the node."""
    from claude_memory.schema import EntityCreateParams

    service.repo.create_node.return_value = {
        "id": ENTITY_ID,
        "name": ENTITY_NAME,
        "salience_score": SALIENCE_DEFAULT,
        "retrieval_count": RETRIEVAL_COUNT_DEFAULT,
    }
    service.repo.get_total_node_count.return_value = 1
    service.ontology = MagicMock()
    service.ontology.is_valid_type.return_value = True

    params = EntityCreateParams(
        name=ENTITY_NAME,
        node_type=ENTITY_TYPE,
        project_id=PROJECT_ID,
    )
    result = await service.create_entity(params)
    assert result.id == ENTITY_ID

    # Verify salience fields were passed to create_node
    call_args = service.repo.create_node.call_args
    props = call_args[0][1]
    assert props["salience_score"] == SALIENCE_DEFAULT
    assert props["retrieval_count"] == RETRIEVAL_COUNT_DEFAULT


async def test_search_fires_salience_async(service: MemoryService) -> None:
    """search() fires salience update as background task — returns pre-update score."""
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "project_id": PROJECT_ID,
                "description": "A language",
                "salience_score": SALIENCE_DEFAULT,
            }
        ],
        "edges": [],
    }
    service.repo.increment_salience.return_value = [
        {
            "id": ENTITY_ID,
            "salience_score": SALIENCE_AFTER_ONE_RETRIEVAL,
            "retrieval_count": 1,
        }
    ]

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT)
    assert len(result) == 1
    # Returns PRE-update salience from graph data (fire-and-forget)
    assert result[0].salience_score == SALIENCE_DEFAULT

    # Let background task complete
    await asyncio.sleep(0)
    # Verify salience was still fired in background
    service.repo.increment_salience.assert_called_once_with([ENTITY_ID])


async def test_search_salience_background_error_silent(service: MemoryService) -> None:
    """When background increment_salience fails, search still returns correctly."""
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "project_id": PROJECT_ID,
                "description": "A language",
                "salience_score": 3.5,
            }
        ],
        "edges": [],
    }
    service.repo.increment_salience.side_effect = ConnectionError("FalkorDB down")

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT)
    assert len(result) == 1
    # Uses graph node's salience_score (background error is silent)
    assert result[0].salience_score == 3.5

    # Let background task complete (should not raise)
    await asyncio.sleep(0)


async def test_search_salience_fallback_default(service: MemoryService) -> None:
    """When no salience_score in graph node, default to 0.0."""
    service.vector_store.search.return_value = [
        {"_id": ENTITY_ID, "_score": PAGERANK_SCORE},
    ]
    service.repo.get_subgraph.return_value = {
        "nodes": [
            {
                "id": ENTITY_ID,
                "name": ENTITY_NAME,
                "node_type": ENTITY_TYPE,
                "project_id": PROJECT_ID,
            }
        ],
        "edges": [],
    }
    service.repo.increment_salience.return_value = []  # No updates returned

    result = await service.search(SEARCH_QUERY, limit=SEARCH_LIMIT)
    assert len(result) == 1
    assert result[0].salience_score == 0.0


def test_base_node_salience_defaults() -> None:
    """BaseNode schema defaults salience_score=1.0 and retrieval_count=0."""
    from claude_memory.schema import BaseNode

    node = BaseNode(name="test", node_type="Concept", project_id="test-proj")
    assert node.salience_score == SALIENCE_DEFAULT
    assert node.retrieval_count == RETRIEVAL_COUNT_DEFAULT


def test_search_result_salience_default() -> None:
    """SearchResult defaults salience_score=0.0."""
    from claude_memory.schema import SearchResult

    result = SearchResult(
        id="test-id",
        name="test",
        node_type="Concept",
        project_id="test-proj",
        score=0.9,
        distance=0.1,
    )
    assert result.salience_score == 0.0


# ─── Temporal Graph Layer Tests ────────────────────────────────────


def test_base_node_occurred_at_default() -> None:
    """BaseNode defaults occurred_at to None."""
    from claude_memory.schema import BaseNode

    node = BaseNode(name="test", node_type="Concept", project_id="proj")
    assert node.occurred_at is None


def test_base_node_occurred_at_set() -> None:
    """BaseNode accepts occurred_at datetime."""
    from datetime import UTC, datetime

    from claude_memory.schema import BaseNode

    ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    node = BaseNode(name="test", node_type="Concept", project_id="proj", occurred_at=ts)
    assert node.occurred_at == ts


def test_concurrent_with_edge_type() -> None:
    """CONCURRENT_WITH is a valid EdgeType."""
    from claude_memory.schema import RelationshipCreateParams

    params = RelationshipCreateParams(
        from_entity="a",
        to_entity="b",
        relationship_type="CONCURRENT_WITH",
    )
    assert params.relationship_type == "CONCURRENT_WITH"


def test_temporal_query_params_defaults() -> None:
    """TemporalQueryParams has correct defaults."""
    from datetime import UTC, datetime

    from claude_memory.schema import TemporalQueryParams

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)
    p = TemporalQueryParams(start=start, end=end)
    assert p.limit == 20
    assert p.project_id is None


def test_temporal_query_params_with_project() -> None:
    """TemporalQueryParams accepts project_id."""
    from datetime import UTC, datetime

    from claude_memory.schema import TemporalQueryParams

    p = TemporalQueryParams(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
        limit=50,
        project_id="my-project",
    )
    assert p.limit == 50
    assert p.project_id == "my-project"


# NOTE: test_query_timeline_no_project removed — used 3-layer deep FalkorDB mock chain
# (select_graph.return_value.query.return_value) and only tested mock calls.


def test_query_timeline_with_project(service: MemoryService) -> None:
    """query_timeline filters by project_id when provided."""
    service.repo.query_timeline.return_value = [
        {"id": ENTITY_ID, "name": ENTITY_NAME, "project_id": PROJECT_ID}
    ]
    result = service.repo.query_timeline(
        start="2026-01-01", end="2026-02-01", project_id=PROJECT_ID
    )
    assert len(result) == 1
    assert result[0]["project_id"] == PROJECT_ID


def test_get_temporal_neighbors_before(service: MemoryService) -> None:
    """get_temporal_neighbors returns predecessors."""
    service.repo.get_temporal_neighbors.return_value = [{"id": "prev-1", "name": "Previous"}]
    result = service.repo.get_temporal_neighbors(ENTITY_ID, direction="before")
    assert len(result) == 1
    service.repo.get_temporal_neighbors.assert_called_once_with(ENTITY_ID, direction="before")


def test_get_temporal_neighbors_after(service: MemoryService) -> None:
    """get_temporal_neighbors returns successors."""
    service.repo.get_temporal_neighbors.return_value = [{"id": "next-1", "name": "Next"}]
    result = service.repo.get_temporal_neighbors(ENTITY_ID, direction="after")
    assert len(result) == 1


def test_get_temporal_neighbors_both(service: MemoryService) -> None:
    """get_temporal_neighbors default direction returns both."""
    service.repo.get_temporal_neighbors.return_value = [{"id": "prev-1"}, {"id": "next-1"}]
    result = service.repo.get_temporal_neighbors(ENTITY_ID)
    assert len(result) == 2


def test_create_temporal_edge_success(service: MemoryService) -> None:
    """create_temporal_edge returns relationship metadata."""
    service.repo.create_temporal_edge.return_value = {
        "rel_type": "PRECEDED_BY",
        "from_id": "entity-a",
        "to_id": "entity-b",
    }
    result = service.repo.create_temporal_edge("entity-a", "entity-b")
    assert result["rel_type"] == "PRECEDED_BY"


def test_create_temporal_edge_not_found(service: MemoryService) -> None:
    """create_temporal_edge returns error when entities not found."""
    service.repo.create_temporal_edge.return_value = {"error": "One or both entities not found"}
    result = service.repo.create_temporal_edge("missing-a", "missing-b")
    assert "error" in result


# ─── Service-Level Temporal Tests ──────────────────────────────────


@pytest.mark.asyncio()
async def test_create_entity_initializes_occurred_at(
    service: MemoryService,
) -> None:
    """create_entity sets occurred_at in properties."""
    from claude_memory.schema import EntityCreateParams

    service.ontology.is_valid_type = MagicMock(return_value=True)
    service.repo.create_node.return_value = {
        "id": "new-id",
        "name": ENTITY_NAME,
        "node_type": "Concept",
    }
    service.embedder.encode.return_value = [0.1] * 384
    service.vector_store.upsert = AsyncMock()
    service.repo.get_total_node_count.return_value = 1

    await service.create_entity(
        EntityCreateParams(
            name=ENTITY_NAME,
            node_type="Concept",
            project_id=PROJECT_ID,
        )
    )
    create_call_props = service.repo.create_node.call_args[0][1]
    assert "occurred_at" in create_call_props


@pytest.mark.asyncio()
async def test_create_entity_respects_user_occurred_at(
    service: MemoryService,
) -> None:
    """create_entity uses user-provided occurred_at value."""
    from claude_memory.schema import EntityCreateParams

    service.ontology.is_valid_type = MagicMock(return_value=True)
    service.repo.create_node.return_value = {
        "id": "new-id",
        "name": ENTITY_NAME,
    }
    service.embedder.encode.return_value = [0.1] * 384
    service.vector_store.upsert = AsyncMock()
    service.repo.get_total_node_count.return_value = 1

    custom_ts = "2026-01-15T12:00:00+00:00"
    await service.create_entity(
        EntityCreateParams(
            name=ENTITY_NAME,
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"occurred_at": custom_ts},
        )
    )
    create_call_props = service.repo.create_node.call_args[0][1]
    assert create_call_props["occurred_at"] == custom_ts


@pytest.mark.asyncio()
async def test_service_query_timeline(service: MemoryService) -> None:
    """MemoryService.query_timeline delegates to repo."""
    from datetime import UTC, datetime

    from claude_memory.schema import TemporalQueryParams

    service.repo.query_timeline.return_value = [{"id": ENTITY_ID, "name": ENTITY_NAME}]
    params = TemporalQueryParams(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
    )
    result = await service.query_timeline(params)
    assert len(result) == 1
    service.repo.query_timeline.assert_called_once()


@pytest.mark.asyncio()
async def test_service_query_timeline_with_project(
    service: MemoryService,
) -> None:
    """MemoryService.query_timeline passes project_id to repo."""
    from datetime import UTC, datetime

    from claude_memory.schema import TemporalQueryParams

    service.repo.query_timeline.return_value = []
    params = TemporalQueryParams(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
        project_id=PROJECT_ID,
    )
    await service.query_timeline(params)
    call_kwargs = service.repo.query_timeline.call_args[1]
    assert call_kwargs["project_id"] == PROJECT_ID


@pytest.mark.asyncio()
async def test_service_get_temporal_neighbors(
    service: MemoryService,
) -> None:
    """MemoryService.get_temporal_neighbors delegates to repo."""
    service.repo.get_temporal_neighbors.return_value = [{"id": "neighbor-1"}]
    result = await service.get_temporal_neighbors(ENTITY_ID, direction="after", limit=5)
    assert len(result) == 1
    service.repo.get_temporal_neighbors.assert_called_once_with(
        entity_id=ENTITY_ID, direction="after", limit=5
    )


# ─── R2: Scoped PRECEDED_BY Tests ──────────────────────────────────


async def test_create_entity_links_preceded_by(service: MemoryService) -> None:
    """create_entity links new entity to most recent in same project via PRECEDED_BY."""
    service.repo.create_node.return_value = {
        "id": "new-entity-id",
        "name": "New Entity",
    }
    service.repo.get_most_recent_entity.return_value = {
        "id": "prev-entity-id",
        "name": "Previous Entity",
    }
    service.repo.create_edge.return_value = {"id": "edge-id"}
    service.repo.get_total_node_count.return_value = 10

    from claude_memory.schema import EntityCreateParams

    params = EntityCreateParams(
        name="New Entity",
        node_type="Concept",
        project_id=PROJECT_ID,
    )
    receipt = await service.create_entity(params)
    assert receipt.id == "new-entity-id"

    # Verify PRECEDED_BY edge was created from prev → new
    found_preceded = False
    for call in service.repo.create_edge.call_args_list:
        if call[0][2] == "PRECEDED_BY":
            assert call[0][0] == "prev-entity-id"
            assert call[0][1] == "new-entity-id"
            found_preceded = True
    assert found_preceded


async def test_create_entity_no_preceded_by_when_first(service: MemoryService) -> None:
    """create_entity skips PRECEDED_BY when no previous entity exists in project."""
    service.repo.create_node.return_value = {
        "id": "first-entity-id",
        "name": "First Entity",
    }
    service.repo.get_most_recent_entity.return_value = None
    service.repo.get_total_node_count.return_value = 1

    from claude_memory.schema import EntityCreateParams

    params = EntityCreateParams(
        name="First Entity",
        node_type="Concept",
        project_id=PROJECT_ID,
    )
    receipt = await service.create_entity(params)
    assert receipt.id == "first-entity-id"

    # create_edge should NOT have been called with PRECEDED_BY
    for call in service.repo.create_edge.call_args_list:
        assert call[0][2] != "PRECEDED_BY"


async def test_create_entity_preceded_by_error_silent(service: MemoryService) -> None:
    """PRECEDED_BY link failure doesn't block entity creation."""
    service.repo.create_node.return_value = {
        "id": "new-id",
        "name": "Entity",
    }
    service.repo.get_most_recent_entity.side_effect = ConnectionError("FalkorDB down")
    service.repo.get_total_node_count.return_value = 5

    from claude_memory.schema import EntityCreateParams

    params = EntityCreateParams(
        name="Entity",
        node_type="Concept",
        project_id=PROJECT_ID,
    )
    # Should not raise despite PRECEDED_BY failure
    receipt = await service.create_entity(params)
    assert receipt.id == "new-id"


# ─── Phase 11D: Message in a Bottle Tests ──────────────────────────


async def test_get_bottles_basic(service: MemoryService) -> None:
    """get_bottles delegates to repo with correct params."""
    from datetime import UTC, datetime

    from claude_memory.schema import BottleQueryParams

    service.repo.get_bottles.return_value = [
        {"id": "bottle-1", "name": "Remember this", "node_type": "Bottle"}
    ]
    params = BottleQueryParams(
        limit=5,
        search_text="remember",
        after_date=datetime(2026, 1, 1, tzinfo=UTC),
    )
    result = await service.get_bottles(params)
    assert len(result) == 1
    assert result[0]["id"] == "bottle-1"
    service.repo.get_bottles.assert_called_once_with(
        limit=5,
        search_text="remember",
        before_date=None,
        after_date="2026-01-01T00:00:00+00:00",
        project_id=None,
    )


async def test_get_bottles_empty(service: MemoryService) -> None:
    """get_bottles returns empty list when no bottles found."""
    from claude_memory.schema import BottleQueryParams

    service.repo.get_bottles.return_value = []
    params = BottleQueryParams()
    result = await service.get_bottles(params)
    assert result == []
