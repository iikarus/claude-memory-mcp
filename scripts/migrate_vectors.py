import asyncio
import logging
import os

from falkordb import FalkorDB
from qdrant_client import AsyncQdrantClient, models

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate() -> None:
    logger.info("Starting Vector Migration: FalkorDB -> Qdrant")

    # Connect to FalkorDB
    falkor_host = os.getenv("FALKORDB_HOST", "localhost")
    falkor_port = int(os.getenv("FALKORDB_PORT", 6379))
    db = FalkorDB(host=falkor_host, port=falkor_port)
    graph = db.select_graph("claude_memory")

    # Connect to Qdrant
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
    client = AsyncQdrantClient(host=qdrant_host, port=qdrant_port)
    collection_name = "memory_embeddings"

    # 1. Fetch all nodes with embeddings from FalkorDB
    logger.info("Fetching nodes from FalkorDB...")
    query = """
    MATCH (n:Entity)
    WHERE n.embedding IS NOT NULL
    RETURN n
    """
    res = graph.query(query)
    nodes = [row[0] for row in res.result_set]
    logger.info(f"Found {len(nodes)} nodes with embeddings.")

    if not nodes:
        util_queries = "MATCH (n) RETURN count(n)"
        count = graph.query(util_queries).result_set[0][0]
        logger.info(f"Total nodes in DB: {count}")
        return

    # 2. Ensure Qdrant Collection
    collections = await client.get_collections()
    if not any(c.name == collection_name for c in collections.collections):
        logger.info(f"Creating collection {collection_name}")
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )

    # 3. Push to Qdrant
    points = []
    for node in nodes:
        props = node.properties
        embedding = props.get("embedding")
        if not embedding:
            continue

        # Clean props for payload (remove heavy embedding and system keys if any)
        payload = props.copy()
        if "embedding" in payload:
            del payload["embedding"]

        points.append(models.PointStruct(id=props["id"], vector=embedding, payload=payload))

    if points:
        logger.info(f"Upserting {len(points)} vectors to Qdrant...")
        await client.upsert(collection_name=collection_name, points=points)
        logger.info("Migration Complete.")
    else:
        logger.info("No valid vectors to migrate.")


if __name__ == "__main__":
    asyncio.run(migrate())
