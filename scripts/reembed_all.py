"""Bulk re-embed all FalkorDB nodes into Qdrant.

Usage:  python scripts/reembed_all.py
Env:    EMBEDDING_API_URL  (default: http://localhost:8001)
        FALKORDB_HOST      (default: localhost)
        QDRANT_HOST        (default: localhost)
"""

import asyncio
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("EMBEDDING_API_URL", "http://localhost:8001")
os.environ.setdefault("FALKORDB_HOST", "localhost")
os.environ.setdefault("QDRANT_HOST", "localhost")

from falkordb import FalkorDB

from src.claude_memory.embedding import EmbeddingService
from src.claude_memory.vector_store import QdrantVectorStore

BATCH_SIZE = 20


async def main() -> None:
    """Pull all nodes from FalkorDB, embed, and upsert into Qdrant."""
    # Connect to FalkorDB
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    db = FalkorDB(host=host, port=port)
    graph = db.select_graph("claude_memory")

    # Services
    embedder = EmbeddingService()
    vs = QdrantVectorStore(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )
    await vs._ensure_collection()

    # Pull all nodes with their properties
    result = graph.query(
        "MATCH (n) RETURN n.id AS id, n.name AS name, "
        "n.node_type AS node_type, n.project_id AS project_id, "
        "n.description AS description"
    )

    nodes = []
    for row in result.result_set:
        nid, name, ntype, pid, desc = row
        if nid and name:
            nodes.append(
                {
                    "id": str(nid),
                    "name": str(name),
                    "node_type": str(ntype or "Entity"),
                    "project_id": str(pid or "default"),
                    "description": str(desc or ""),
                }
            )

    print(f"[INFO] Found {len(nodes)} nodes with id+name in FalkorDB")

    # Batch embed and upsert
    success = 0
    errors = 0
    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i : i + BATCH_SIZE]
        texts = [f"{n['name']} {n['node_type']} {n['description']}" for n in batch]

        try:
            vectors = embedder.encode_batch(texts)
        except Exception as e:
            print(f"[ERROR] Embedding batch {i}-{i + len(batch)}: {e}")
            errors += len(batch)
            continue

        for node, vec in zip(batch, vectors, strict=True):
            payload = {
                "name": node["name"],
                "node_type": node["node_type"],
                "project_id": node["project_id"],
            }
            try:
                await vs.upsert(id=node["id"], vector=vec, payload=payload)
                success += 1
            except Exception as e:
                print(f"[ERROR] Upsert {node['id']}: {e}")
                errors += 1

        print(f"  [{i + len(batch)}/{len(nodes)}] embedded")

    print(f"\n[DONE] Re-embedded {success} vectors, {errors} errors")


if __name__ == "__main__":
    asyncio.run(main())
