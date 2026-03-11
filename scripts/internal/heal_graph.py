import asyncio
import os

from claude_memory.clustering import ClusteringService
from claude_memory.embedding import EmbeddingService
from claude_memory.librarian import LibrarianAgent
from claude_memory.tools import MemoryService


async def run_healer() -> None:
    print("🩹 Starting Graph Healing (Librarian Cycle)...")

    # 1. Initialize Dependency Tree
    # Ensure point to remote embeddings if available, or local
    # We are running as a script, so we might not have the env var set in shell?
    # Actually we should assume the docker containers are "up", so we can use http://localhost:8001

    if not os.getenv("EMBEDDING_API_URL"):
        # For local script running against dockerized embeddings
        os.environ["EMBEDDING_API_URL"] = "http://localhost:8001"

    # Force Localhost for generic scripts
    os.environ["FALKORDB_HOST"] = "localhost"
    os.environ["FALKORDB_PORT"] = "6379"
    os.environ["QDRANT_HOST"] = "localhost"
    os.environ["QDRANT_PORT"] = "6333"

    print("   Initializing Services...")
    embedder = EmbeddingService()
    service = MemoryService(embedding_service=embedder)
    clustering = ClusteringService()
    librarian = LibrarianAgent(service, clustering)

    # 2. Run Cycle
    print("   Running cycle...")
    stats = await librarian.run_cycle()

    print("\n✨ Healing Complete.")
    print(f"   Clusters Found: {stats.get('clusters_found', 0)}")
    print(f"   Consolidations: {stats.get('consolidations_created', 0)}")

    if stats.get("errors"):
        print(f"   ⚠️ Errors: {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(run_healer())
