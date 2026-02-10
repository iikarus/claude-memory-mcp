import asyncio
import logging
import os
import sys

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from claude_memory.embedding import EmbeddingService
from claude_memory.schema import EntityCreateParams
from claude_memory.tools import MemoryService

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("E2E_Test")


async def run_e2e() -> None:
    logger.info("=== STARTING END-TO-END TEST (LIVE INFRASTRUCTURE) ===")

    # 1. Initialize Real Services (No Mocks)
    # Assumes Docker containers are running on localhost:6379 (Falkor) and localhost:6333 (Qdrant)
    # The services read env vars or default to localhost

    logger.info("[1/5] Initializing Services...")
    try:
        embedder = EmbeddingService()  # Real SentenceTransformer
        service = MemoryService(embedding_service=embedder)  # Real Repo + Real VectorStore
        logger.info("✅ Services Initialized.")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize services: {e}")
        return

    # 2. Create Project
    logger.info("[2/5] Creating Test Project...")
    project_id = "e2e_test_project"
    try:
        p_params = EntityCreateParams(
            name="E2E Test Project",
            node_type="Project",
            project_id=project_id,
            properties={"desc": "Temporary project for E2E validation"},
        )
        project = await service.create_entity(p_params)
        logger.info(f"✅ Project Created: {project.id}")
    except Exception as e:
        logger.critical(f"❌ Failed to create project: {e}")
        return

    # 3. Add Entity (Memory)
    logger.info("[3/5] Adding Test Entity...")
    try:
        e_params = EntityCreateParams(
            name="E2E Artifact",
            node_type="Entity",
            project_id=project_id,
            properties={"content": "The E2E test verifies the full stack connection."},
        )
        entity = await service.create_entity(e_params)
        logger.info(f"✅ Entity Created: {entity.id}")
    except Exception as e:
        logger.critical(f"❌ Failed to create entity: {e}")
        return

    # 4. Verify Vector Search
    logger.info("[4/5] Verifying Vector Search...")
    try:
        # Give a small delay for indexing if async? (Should be awaitable)
        results = await service.search("stack connection", project_id=project_id, limit=5)

        found = False
        for res in results:
            if res.id == entity.id:
                found = True
                logger.info(f" -> Found match: {res.name} (Score: {res.score:.4f})")
                break

        if found:
            logger.info("✅ Vector Search Successful.")
        else:
            logger.error("❌ Vector Search failed to find the created entity.")
            logger.info(f"Results: {results}")

    except Exception as e:
        logger.critical(f"❌ Failed during search: {e}")
        return

    # 5. Verify Graph Persistence
    logger.info("[5/5] Verifying Graph Persistence...")
    try:
        # We can simulate this by fetching neighbors or using get_node if available
        # Implementation Detail: create_relationship would prove graph write/read
        # Let's try creating a relationship to the project
        from claude_memory.schema import RelationshipCreateParams

        r_params = RelationshipCreateParams(
            from_entity=entity.id, to_entity=project.id, relationship_type="BELONGS_TO_PROJECT"
        )
        await service.create_relationship(r_params)
        logger.info("✅ Relationship Created (Graph Write Verified).")

        # Read back neighbors
        neighbors = await service.get_neighbors(entity.id)
        project_neighbor = next((n for n in neighbors if n["id"] == project.id), None)

        if project_neighbor:
            logger.info("✅ Graph Read Verified (Neighbor found).")
        else:
            logger.error("❌ Graph Read Failed (Neighbor not found).")

    except Exception as e:
        logger.critical(f"❌ Failed during graph operations: {e}")
        return

    logger.info("=== E2E TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(run_e2e())
