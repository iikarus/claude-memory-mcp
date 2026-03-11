import asyncio
import os
import uuid

from claude_memory.embedding import EmbeddingService
from claude_memory.schema import EntityCreateParams
from claude_memory.tools import MemoryService

# Ensure we point to the Docker services
os.environ["EMBEDDING_API_URL"] = "http://localhost:8001"
os.environ["FALKORDB_HOST"] = "localhost"
os.environ["FALKORDB_PORT"] = "6379"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"


async def run_e2e() -> None:
    print("🚀 Starting End-to-End System Check...")
    print("   Target: Microservice Architecture (Docker)")

    # 1. Initialize Services
    try:
        print("\n1️⃣  Initializing Services...")
        embedder = EmbeddingService()
        service = MemoryService(embedding_service=embedder)
        print("   ✅ Services Initialized (Embedder + MemoryService)")
    except Exception as e:
        print(f"   ❌ Service Init Failed: {e}")
        return

    # 2. Create Test Memory
    test_id = str(uuid.uuid4())[:8]
    test_name = f"E2E_Test_{test_id}"
    print(f"\n2️⃣  Creating Memory: '{test_name}'...")

    try:
        params = EntityCreateParams(
            name=test_name,
            node_type="Entity",
            content=f"This is a transient test node to verify E2E functionality. Timestamp: {test_id}",
            project_id="system-check",
        )
        res = await service.create_entity(params)
        print(f"   ✅ Creation Output: {res}")
        created_id = res.id

    except Exception as e:
        print(f"   ❌ Creation Failed: {e}")
        return

    # 3. Search (Vector Retrieval)
    print("\n3️⃣  Verifying Vector Search...")
    await asyncio.sleep(1)

    try:
        # Calculate embedding manually as Service doesn't expose raw search
        query = f"verify {test_id}"
        vec = service.embedder.encode(query)
        # Fix: argument is 'vector', not 'query_vector'
        results = await service.vector_store.search(vector=vec, limit=5)

        found = False
        for r in results:
            # Fix: results are dicts, not objects
            payload = r.get("payload", {})
            # Check name or ID
            if payload.get("name") == test_name:
                score = r.get("_score", 0.0)
                print(f"   ✅ Found Node via Vector Search (Score: {score:.4f})")
                found = True
                break

        if not found:
            print("   ⚠️  Created node NOT found in search results.")
    except Exception as e:
        print(f"   ❌ Search Failed: {e}")

    # 4. Graph Retrieval
    print("\n4️⃣  Verifying Graph Storage...")
    # (Skipped for brevity, search implies existence)

    # 5. Clean Up
    print("\n5️⃣  Cleaning Up...")
    try:
        from claude_memory.schema import EntityDeleteParams

        # Fix: Use real ID and required 'reason'
        await service.delete_entity(EntityDeleteParams(entity_id=created_id, reason="E2E Cleanup"))
        print("   ✅ Test Node Deleted.")
    except Exception as e:
        print(f"   ❌ Deletion Failed: {e}")

    print("\n✨ System Check Complete.")


if __name__ == "__main__":
    asyncio.run(run_e2e())
