import asyncio
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from claude_memory.server import service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def verify() -> None:
    logger.info("Verifying system...")

    # Test 1: Get Entity from Seed
    # Since we don't have direct get_by_name in service yet (only search), we use search
    logger.info("Test 1: Search for 'Tabish'")
    results = await service.search("Tabish", limit=1)
    if results:
        e = results[0]
        logger.info(f"✅ Found: {e.name} ({e.node_type}) - Score: {e.score}")
    else:
        logger.error("❌ Test 1 Failed: Tabish not found")

    # Test 2: Semantic Search (Hybrid)
    logger.info("Test 2: Semantic search for 'Director'")
    results = await service.search("someone who directs", limit=5)
    found = any(r.name == "Tabish" for r in results)
    if found:
        logger.info("✅ Semantic search working (found Tabish for 'someone who directs')")
    else:
        logger.error("❌ Test 2 Failed: Semantic search didn't return expected results")


if __name__ == "__main__":
    asyncio.run(verify())
