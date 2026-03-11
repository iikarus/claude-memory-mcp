import asyncio
import os

from qdrant_client import QdrantClient

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
FALKOR_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKOR_PORT = int(os.getenv("FALKORDB_PORT", 6379))
COLLECTION_NAME = "memory_embeddings"


async def recover_graph() -> None:
    print("🚑 Starting Emergency Graph Recovery...")
    print(f"   Source: Qdrant ({QDRANT_HOST}:{QDRANT_PORT})")
    print(f"   Target: FalkorDB ({FALKOR_HOST}:{FALKOR_PORT})")

    # Connect to Clients
    q_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # 1. Fetch All Vectors (Batch scroll)
    print("   Fetching vectors...", end=" ", flush=True)
    points = []
    offset = None
    while True:
        res, next_offset = q_client.scroll(
            collection_name=COLLECTION_NAME,
            offset=offset,
            limit=100,
            with_payload=True,
            with_vectors=True,
        )
        points.extend(res)
        offset = next_offset
        if offset is None:
            break
    print(f"✅ Found {len(points)} vectors.")

    # 2. Re-create Nodes in FalkorDB
    print("   Reconstructing Graph Nodes...", end=" ", flush=True)
    success_count = 0

    for pt in points:
        try:
            entity_id = str(pt.id)
            payload = pt.payload or {}

            name = payload.get("name", "Unknown Entity")
            node_type = payload.get("node_type", "Entity")
            project_id = payload.get("project_id", "default")
            content = payload.get("content", "")  # might be missing

            # Sanitize for Cypher
            name = name.replace("'", "\\'")
            content = content.replace("'", "\\'")

            # Cypher Query
            # Using GRAPH.QUERY command via Redis client
            query = f"""
            MERGE (n:Entity {{id: '{entity_id}'}})
            SET n.name = '{name}',
                n.type = '{node_type}',
                n.project_id = '{project_id}',
                n.description = '{content}'
            RETURN n
            """

            # Execute raw graph query
            # Note: falkordb-py would be cleaner but direct redis is robust here
            # We use falkordb-py usually, but let's assume we can use the library if installed
            # Actually, let's use the installed falkordb library to be safe with quoting
            pass

        except Exception as e:
            print(f"Failed to process {pt.id}: {e}")

    # Let's switch to using the actual FalkorDB client library for safety
    from falkordb import FalkorDB

    db = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT)
    g = db.select_graph("claude_memory")

    for pt in points:
        try:
            entity_id = str(pt.id)
            payload = pt.payload or {}

            # Extract
            vector = pt.vector
            # Ensure vector is a list
            if hasattr(vector, "tolist"):
                vector = vector.tolist()

            props = {
                "id": entity_id,
                "name": payload.get("name", "Unknown"),
                "type": payload.get("node_type", "Entity"),
                "project_id": payload.get("project_id", "default"),
                "description": payload.get("content", "") or payload.get("description", ""),
                "embedding": vector,
            }

            query = """
            MERGE (n:Entity {id: $id})
            SET n += $props
            """
            g.query(query, {"id": entity_id, "props": props})
            success_count += 1
            if success_count % 10 == 0:
                print(".", end="", flush=True)

        except Exception as e:
            print(f"\n❌ Error on {pt.id}: {e}")

    print(f"\n✨ Recovery Complete. Restored {success_count} nodes.")


if __name__ == "__main__":
    asyncio.run(recover_graph())
