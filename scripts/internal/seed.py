import asyncio
import logging
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from claude_memory.schema import EntityCreateParams
from claude_memory.server import service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed() -> None:
    logger.info("Starting data seed...")

    # Define initial entities
    entities = [
        EntityCreateParams(
            name="TestUser",
            node_type="Person",
            project_id="meta",
            properties={
                "role": "Director/Student",
                "learning_style": "visual-spatial, analogy-driven",
                "communication": "direct, informal, intellectual sparring",
            },
            certainty="confirmed",
        ),
        EntityCreateParams(
            name="Claude",
            node_type="Person",
            project_id="meta",
            properties={
                "role": "Teacher/Partner/Co-architect",
                "teaching_style": "pirates and builders, patient, celebrates breakthroughs",
            },
            certainty="confirmed",
        ),
        EntityCreateParams(
            name="Code Literacy",
            node_type="Project",
            project_id="literacy",
            properties={
                "goal": "Read, evaluate, and direct code without writing it",
                "status": "active",
            },
            certainty="confirmed",
        ),
    ]

    for entity in entities:
        logger.info(f"Seeding entity: {entity.name}")
        try:
            await service.create_entity(entity)
            logger.info(f"Successfully created {entity.name}")
        except Exception as e:
            logger.error(f"Failed to create {entity.name}: {e}")

    logger.info("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
