import asyncio
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from claude_memory.tools import EntityCreateParams, MemoryService  # noqa: E402

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)


async def debug_pagerank() -> None:
    service = MemoryService()
    print("Resetting DB for clean test...")
    service.repo.execute_cypher("MATCH (n) DETACH DELETE n")

    print("Creating graph...")
    # A->B
    a = await service.create_entity(
        EntityCreateParams(name="Node A", node_type="Concept", project_id="debug")
    )
    b = await service.create_entity(
        EntityCreateParams(name="Node B", node_type="Concept", project_id="debug")
    )

    # Create relationship manually or via tool
    service.repo.create_edge(a["id"], b["id"], "LINKS_TO", {})

    print("Running PageRank...")
    # Run raw query to check syntax
    try:
        service.repo.execute_cypher("CALL algo.pageRank('Entity', 'rank')")
        print("PageRank CALL executed.")
    except Exception as e:
        print(f"PageRank CALL failed: {e}")

    print("Checking properties...")
    res = service.repo.execute_cypher("MATCH (n:Entity) RETURN n.name, n.rank")
    for row in res.result_set:
        print(f"Node: {row[0]}, Rank: {row[1]}")


if __name__ == "__main__":
    asyncio.run(debug_pagerank())
