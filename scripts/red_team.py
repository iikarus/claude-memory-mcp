import asyncio
import logging
import random
import string
import time

from claude_memory.embedding import EmbeddingService
from claude_memory.schema import EntityCreateParams, RelationshipCreateParams
from claude_memory.tools import MemoryService

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RedTeam")

# Initialize Service
logger.info("Initializing Service...")
embedder = EmbeddingService()
service = MemoryService(embedding_service=embedder)


def generate_random_string(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


async def test_fuzzing() -> None:
    logger.info("\n--- TEST 1: CHAOS FUZZING ---")

    project_id = "chaos_project"

    # CASE 1: Emojis & Special Chars
    logger.info("[1.1] Creating Entity with Emojis and SQL-like chars...")
    name = "Project 🚀 Tables DROP TABLE users; --"
    try:
        params = EntityCreateParams(
            name=name,
            node_type="Project",
            project_id=project_id,
            properties={"desc": "Anarchy 🏴‍☠️"},
        )
        await service.create_entity(params)
        logger.info("✅ Handled Emojis/Special Chars gracefully.")
    except Exception as e:
        logger.error(f"❌ Failed on Emojis: {e}")

    # CASE 2: Empty Strings
    logger.info("[1.2] Creating Entity with Empty Name...")
    try:
        params = EntityCreateParams(
            name="",
            node_type="Project",
            project_id=project_id,
        )
        await service.create_entity(params)
        logger.warning("⚠️ Creation with empty name succeeded (Should validation prevent this?)")
    except Exception as e:
        logger.info(f"✅ Handled Empty Name gracefully: {e}")

    # CASE 3: Massive Payload (100KB)
    logger.info("[1.3] Creating Entity with Massive Payload (100KB)...")
    huge_desc = generate_random_string(100 * 1024)
    try:
        start = time.time()
        params = EntityCreateParams(
            name="Big Data",
            node_type="Entity",
            project_id=project_id,
            properties={"data": huge_desc},
        )
        await service.create_entity(params)
        duration = time.time() - start
        logger.info(f"✅ Created 100KB payload in {duration:.2f}s")
    except Exception as e:
        logger.error(f"❌ Failed on Massive Payload: {e}")


async def test_concurrency() -> None:
    logger.info("\n--- TEST 2: CONCURRENCY STRESS ---")
    project_id = "stress_project"

    # Setup
    create_params = EntityCreateParams(
        name="Concurrent Target", node_type="Entity", project_id=project_id
    )
    await service.create_entity(create_params)
    # Ideally get the real ID, but for now we search or assume created
    res = await service.search("Concurrent Target")
    if not res:
        logger.error("❌ Setup failed")
        return
    real_id = res[0]["id"]

    async def fast_update(idx: int) -> bool:
        try:
            await service.update_entity(real_id, {"counter": idx})
            # logger.info(f"Update {idx} success")
            return True
        except Exception as e:
            logger.warning(f"Update {idx} failed: {e}")
            return False

    logger.info(f"🚀 Launching 10 parallel updates on {real_id}...")
    start = time.time()
    results = await asyncio.gather(*[fast_update(i) for i in range(10)])
    duration = time.time() - start

    success_count = sum(results)
    logger.info(f"Analysis: {success_count}/10 updates succeeded in {duration:.2f}s")
    if success_count == 10:
        logger.info("✅ Mechanism is robust (Queueing worked or Redis lock handled retry).")
    else:
        logger.warning(
            "⚠️ Some updates failed (Lock contention?). This is expected behavior for strict locking."
        )


async def test_cycles() -> None:
    logger.info("\n--- TEST 3: GRAPH CYCLES ---")
    project_id = "cycle_lab"

    # Create A->B->C->A
    logger.info("Creating Ring Topology...")
    a_params = EntityCreateParams(name="Node A", node_type="Entity", project_id=project_id)
    a = await service.create_entity(a_params)
    b_params = EntityCreateParams(name="Node B", node_type="Entity", project_id=project_id)
    b = await service.create_entity(b_params)
    c_params = EntityCreateParams(name="Node C", node_type="Entity", project_id=project_id)
    c = await service.create_entity(c_params)

    await service.create_relationship(
        RelationshipCreateParams(from_entity=a.id, to_entity=b.id, relationship_type="RELATED_TO")
    )
    await service.create_relationship(
        RelationshipCreateParams(from_entity=b.id, to_entity=c.id, relationship_type="RELATED_TO")
    )
    await service.create_relationship(
        RelationshipCreateParams(from_entity=c.id, to_entity=a.id, relationship_type="RELATED_TO")
    )

    logger.info(" traversing neighbors (infinite loop check)...")
    try:
        # Assuming get_hologram or neighbors handles visited set
        neighbors = await service.get_neighbors(a.id, depth=5)
        logger.info(f"✅ Traversal returned {len(neighbors)} nodes. No infinite loop.")
    except RecursionError:
        logger.error("❌ Infinite Loop Detected!")
    except Exception as e:
        logger.error(f"❌ Traversal crashed: {e}")


async def main() -> None:
    logger.info("🔴 STARTING RED TEAM OPERATIONS 🔴")
    try:
        await test_fuzzing()
        await test_concurrency()
        await test_cycles()
    except Exception as e:
        logger.critical(f"🔥 UNHANDLED SYSTEM CRASH: {e}")
    finally:
        logger.info("🛑 Red Team Operations Complete.")


if __name__ == "__main__":
    asyncio.run(main())
