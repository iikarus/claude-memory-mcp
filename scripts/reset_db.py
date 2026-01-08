import logging
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from claude_memory.repository import MemoryRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import inspect

print(f"DEBUG source: {inspect.getsource(MemoryRepository.ensure_indices)}")


def reset_database():
    """
    Drops the existing graph and re-initializes indices.
    WARNING: This deletes all data!
    """
    logger.warning("Starting Database Reset...")

    repo = MemoryRepository()

    # 1. Drop Graph
    try:
        g = repo.select_graph()
        g.delete()  # This returns None or string response
        logger.info(f"Graph '{repo.graph_name}' deleted successfully.")
    except Exception as e:
        logger.warning(f"Could not delete graph (might not exist): {e}")

    # 2. Re-create Indices (triggered by ensure_indices)
    logger.info("Re-creating indices with new settings...")
    try:
        repo.ensure_indices()
        logger.info("Indices created successfully (Dimension: 768).")
    except Exception as e:
        logger.error(f"Failed to create indices: {e}")

    logger.info("Database reset complete.")


if __name__ == "__main__":
    reset_database()
