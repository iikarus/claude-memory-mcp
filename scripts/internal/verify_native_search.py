import asyncio
import os
import sys

from claude_memory.schema import EntityCreateParams
from claude_memory.tools import MemoryService

# Ensure we can import the src module
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


async def verify_native_search() -> None:
    print("Initializing MemoryService...")
    service = MemoryService()

    # Give it a moment for index creation (though it's usually blocking/fast)
    await asyncio.sleep(1)

    # 1. Create a test entity
    print("Creating test entity...")
    params = EntityCreateParams(
        name="VectorTest Entity", node_type="Concept", project_id="test_vector"
    )
    # We add a description to ensure good embedding content
    params.properties = {
        "description": "This is a unique entity for verifying native vector search functionality."
    }

    res = await service.create_entity(params)
    print(f"Entity created: {res['id']}")

    # 2. Search for it
    print("Searching for 'unique entity verifying functionality'...")
    # This query semantic matches the description
    results = await service.search("unique entity verifying functionality", limit=5)

    found = False
    for r in results:
        print(f"Found: {r.name} (Score: {r.score}) - Type: {r.node_type}")
        if r.id == res["id"]:
            found = True

    if found:
        print("✅ Native Vector Search Verified! (Found target entity)")
    else:
        print("❌ Search Failed. Target entity not found.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify_native_search())
