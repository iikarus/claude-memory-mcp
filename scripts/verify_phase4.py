import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from claude_memory.schema import EntityCreateParams, RelationshipCreateParams
from claude_memory.tools import MemoryService

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


async def verify_phase4() -> None:
    print("Initializing MemoryService...")
    service = MemoryService()

    # 1. Setup Graph for PageRank
    print("\n--- 1. Setup Graph (A->B->C) ---")
    # A points to B, C points to B. B should have high rank.
    a = await service.create_entity(
        EntityCreateParams(name="Node A", node_type="Concept", project_id="test_phase4")
    )
    b = await service.create_entity(
        EntityCreateParams(name="Node B", node_type="Concept", project_id="test_phase4")
    )
    c = await service.create_entity(
        EntityCreateParams(name="Node C", node_type="Concept", project_id="test_phase4")
    )

    await service.create_relationship(
        RelationshipCreateParams(
            from_entity=a["id"],
            to_entity=b["id"],
            relationship_type="DEPENDS_ON",
            properties={"confidence": 0.8},
        )
    )
    await service.create_relationship(
        RelationshipCreateParams(
            from_entity=c["id"],
            to_entity=b["id"],
            relationship_type="DEPENDS_ON",
            properties={"confidence": 0.9},
        )
    )
    print("Graph created.")

    # 2. Test Analyze Graph (PageRank)
    print("\n--- 2. Testing analyze_graph(pagerank) ---")
    results = await service.analyze_graph("pagerank")
    print(f"Top nodes by rank: {len(results)}")
    found_b = False
    for r in results:
        if "error" in r:
            print(f"❌ Error in PageRank: {r['error']}")
            continue
        print(f" - {r['name']}: {r.get('rank', 0)}")
        if r["name"] == "Node B":
            found_b = True

    if found_b:
        print("✅ PageRank Verified (Results returned).")
    else:
        print("⚠️ PageRank ran but didn't identify Node B (Might need more iterations or time).")

    # 3. Test Stale Entities
    print("\n--- 3. Testing get_stale_entities ---")
    # Manually insert a stale node via client
    # ACCESS via repo.client or repo.execute_cypher (cleaner)
    old_date = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    q = """
    CREATE (n:Entity {id: 'stale-1', name: 'Stale Node', updated_at: $old_date, status: 'active', project_id: 'test_phase4'})
    RETURN n
    """
    service.repo.execute_cypher(q, {"old_date": old_date})
    print("Inserted 'Stale Node' manually.")

    stale = await service.get_stale_entities(days=30)
    print(f"Stale entities found: {len(stale)}")
    if any(e["name"] == "Stale Node" for e in stale):
        print("✅ get_stale_entities Verified.")
    else:
        print("❌ Stale node not found!")

    # 4. Test Consolidation
    print("\n--- 4. Testing consolidate_memories ---")
    summary = "Consolidation of Node A and Node C"
    cons_node = await service.consolidate_memories([a["id"], c["id"]], summary)
    print(f"Consolidated Node Created: {cons_node['name']} ({cons_node['id']})")

    # Verify links
    # Use repo.execute_cypher
    q_check = "MATCH (a)-[:PART_OF]->(c) WHERE c.id = $cid RETURN count(a)"
    res = service.repo.execute_cypher(q_check, {"cid": cons_node["id"]})
    links = res.result_set[0][0]
    print(f"Linked entities count: {links}")

    if links >= 2:
        print("✅ consolidate_memories Verified.")
    else:
        print("❌ Consolidation links missing.")

    # Cleanup optional


if __name__ == "__main__":
    asyncio.run(verify_phase4())
