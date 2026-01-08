from unittest.mock import MagicMock, patch

import pytest

from claude_memory.schema import (
    BreakthroughParams,
    EntityCreateParams,
    ObservationParams,
    SessionEndParams,
    SessionStartParams,
)
from claude_memory.tools import MemoryService


@pytest.fixture
def memory_service():
    # Patch FalkorDB in the REPOSITORY module and EmbeddingService in TOOLS
    with (
        patch("claude_memory.repository.FalkorDB") as mock_db,
        patch("claude_memory.embedding.EmbeddingService") as mock_embedder_cls,
    ):

        # Mock DB
        mock_client = MagicMock()
        mock_db.return_value = mock_client
        mock_client.select_graph.return_value = MagicMock()

        # Mock Embedder
        mock_embedder = MagicMock()
        mock_embedder_cls.return_value = mock_embedder
        mock_embedder.encode.return_value = [0.1] * 1024

        service = MemoryService()
        # Ensure our mock is the one used (via constructor default)
        service.embedder = mock_embedder

        yield service


@pytest.mark.asyncio  # type: ignore
async def test_day_in_the_life(memory_service):
    """Simulates a full user workflow."""
    # Access graph via repo
    graph = memory_service.repo.client.select_graph.return_value

    # Patch UUID generation to return deterministic IDs

    # Patch UUID generation to return deterministic IDs
    # Sequence:
    # 1. create_entity -> calls uuid (if implemented) OR we mock DB return.
    #    create_entity returns DB props. If mock DB returns "cnt-1", it matches.
    #    BUT internal logic might use UUID. Let's patch globally in this test.

    with patch(
        "uuid.uuid4", side_effect=["cnt-1", "sess-1", "obs-1", "bk-1", "other-1", "other-2"]
    ):
        # 1. Create Entity (Project)
        # Mock what the DB *returns* (which should match what we insert if logic relies on DB return)
        graph.query.return_value.result_set = [
            [MagicMock(properties={"id": "cnt-1", "name": "Content"})]
        ]

        e_params = EntityCreateParams(
            name="Project Tesseract", node_type="Project", project_id="meta"
        )
        res_entity = await memory_service.create_entity(e_params)
        # If create_entity uses uuid inside, it got 'cnt-1'.
        # If it returns DB result, it gets 'cnt-1' from our mock.
        assert res_entity["id"] == "cnt-1"

        # 2. Start Session (uses uuid) -> Get 'sess-1'
        # Mock DB return
        session_mock = MagicMock()
        session_mock.properties = {"id": "sess-1", "status": "active"}
        graph.query.return_value.result_set = [[session_mock]]

        s_params = SessionStartParams(project_id="meta", focus="Coding")
        res_session = await memory_service.start_session(s_params)
        assert res_session["id"] == "sess-1"

        # 3. Add Observation (uses uuid) -> Get 'obs-1'
        # Mock DB return
        obs_mock = MagicMock()
        obs_mock.properties = {"id": "obs-1", "content": "It works"}
        graph.query.return_value.result_set = [[obs_mock]]

        o_params = ObservationParams(entity_id="cnt-1", content="It works")
        res_obs = await memory_service.add_observation(o_params)
        assert res_obs["id"] == "obs-1"

        # 4. Record Breakthrough (uses uuid) -> Get 'bk-1'
        # Mock DB return might not be used for ID if it returns constructed dict,
        # but for consistency we mock DB return too.
        bk_mock = MagicMock()
        bk_mock.properties = {"id": "bk-1", "name": "Eureka"}
        graph.query.return_value.result_set = [[bk_mock]]

        b_params = BreakthroughParams(name="Eureka", moment="Now", session_id="sess-1")
        res_bk = await memory_service.record_breakthrough(b_params)
        assert res_bk["id"] == "bk-1"

        # 5. End Session
        # Mock return
        sess_closed_mock = MagicMock()
        sess_closed_mock.properties = {"id": "sess-1", "status": "closed"}
        graph.query.return_value.result_set = [[sess_closed_mock]]

        se_params = SessionEndParams(session_id="sess-1", summary="Done")
        res_end = await memory_service.end_session(se_params)
        assert res_end["status"] == "closed"

        # Verify calls happened (basic check)
        assert graph.query.call_count >= 5
