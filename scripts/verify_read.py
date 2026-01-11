import asyncio
from typing import List

from claude_memory.interfaces import Embedder
from claude_memory.tools import MemoryService
from claude_memory.vector_store import QdrantVectorStore


# Mock Embedder (Must return same dim as index)
class MockVerifyEmbedder(Embedder):  # type: ignore
    def encode(self, text: str) -> List[float]:
        # FalkorDB index created with 1024 dims in repository.py
        # We need to return non-zero vector to ensure similarity works if using cosine
        return [0.1] * 1024


async def main() -> None:
    print("🧪 Verifying Read/Search Logic...")

    # Inject dependencies manually for script usage
    # falkor = MemoryRepository(host="localhost", port=6379, password=None)  <-- Unused
    embedder = MockVerifyEmbedder()
    qdrant = QdrantVectorStore(host="localhost", port=6333)

    service = MemoryService(embedding_service=embedder, vector_store=qdrant, host="localhost")

    # Test 1: Direct ID Read (using cypher via execute_cypher unless get_entity exists)
    # searching for "Singularity Point" from previous step
    # We don't know the ID, so let's query by name first.

    print("\n[1] Check presence by Name (Cypher)...")
    res = service.repo.execute_cypher("MATCH (n:Entity {name: 'Singularity Point'}) RETURN n")
    if not res.result_set:
        print("❌ FAILED: 'Singularity Point' not found in DB via Cypher!")
    else:
        node = res.result_set[0][0]
        print(f"✅ FOUND: {node.properties['name']} (ID: {node.properties['id']})")

        # Test 2: Vector Search
        print("\n[2] Testing Vector Search...")
        # We mock embedding so query vector is [0.1...].
        # Node vector should also be [0.1...] if created with Mock in verify_dedup.py.
        # Wait: verify_dedup.py used Mock.
        # Real Claude uses real embedding.
        # If we replaced tools.py to inject Mock, Real Claude would break.
        # But we injected Mock only in test scripts.
        # Tools.py imports interfaces.
        # Initialization in server.py uses `EmbeddingService()` which is real (or stub if no API key).

        # Issue: If `verify_dedup.py` wrote "Singularity Point" with Mock Embedding ([0.1...]),
        # and Real Claude tries to search with Real Embedding (SentenceTransformer),
        # the vectors will be totally different dimensions or just orthogonal.
        # FalkorDB index is dimension fixed?

        # Let's see what happens.
        results = await service.search("Singularity", limit=5)
        if not results:
            print("⚠️  WARNING: Search returned 0 results.")
            print("   - Possible cause: Embedding mismatch or Index empty.")
        else:
            print(f"✅ SEARCH SUCCESS: Found {len(results)} items.")
            for r in results:
                print(f"   - {r.name} (Score: {r.score:.4f})")


if __name__ == "__main__":
    asyncio.run(main())
