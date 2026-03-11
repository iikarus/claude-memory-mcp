"""Backfill observation embeddings into Qdrant.

Scans all Observation nodes in FalkorDB that are NOT yet in Qdrant
and embeds + upserts them.  This is the retroactive companion to the
E-3 feature (observation vectorization on creation).

Usage:  python scripts/embed_observations.py [--dry-run]
Env:    EMBEDDING_API_URL  (default: http://localhost:8001)
        FALKORDB_HOST      (default: localhost)
        QDRANT_HOST        (default: localhost)
"""

import asyncio
import os
import sys

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("EMBEDDING_API_URL", "http://localhost:8001")
os.environ.setdefault("FALKORDB_HOST", "localhost")
os.environ.setdefault("QDRANT_HOST", "localhost")

from falkordb import FalkorDB

from claude_memory.embedding import EmbeddingService
from claude_memory.vector_store import QdrantVectorStore

BATCH_SIZE = 5


async def main(*, dry_run: bool = False) -> None:  # noqa: C901, PLR0912
    """Pull all observations from FalkorDB, embed, and upsert into Qdrant."""
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

    # Pull all observations with their parent entity info
    result = graph.query(
        "MATCH (e:Entity)-[:HAS_OBSERVATION]->(o) "
        "RETURN o.id AS id, o.content AS content, "
        "e.id AS entity_id, e.project_id AS project_id"
    )

    observations = []
    for row in result.result_set:
        obs_id, content, entity_id, project_id = row
        if obs_id and content:
            observations.append(
                {
                    "id": str(obs_id),
                    "content": str(content),
                    "entity_id": str(entity_id or ""),
                    "project_id": str(project_id or "default"),
                }
            )

    print(f"[INFO] Found {len(observations)} observations in FalkorDB")

    if not observations:
        print("[DONE] Nothing to backfill.")
        return

    # Check which observations already have Qdrant vectors (idempotent)
    existing_ids: set[str] = set()
    for obs in observations:
        try:
            points = await vs._client.retrieve(
                collection_name="memory_embeddings",
                ids=[obs["id"]],
                with_payload=False,
                with_vectors=False,
            )
            if points:
                existing_ids.add(obs["id"])
        except Exception:  # noqa: S110
            pass  # Point doesn't exist, needs embedding

    missing = [o for o in observations if o["id"] not in existing_ids]
    print(f"[INFO] {len(existing_ids)} already embedded, {len(missing)} need backfill")

    if dry_run:
        print("[DRY-RUN] Would embed the following observations:")
        for obs in missing[:10]:
            print(f"  {obs['id']}: {obs['content'][:60]}...")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return

    # Batch embed and upsert
    success = 0
    errors = 0
    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        texts = [o["content"] for o in batch]

        try:
            vectors = embedder.encode_batch(texts)
        except Exception as e:
            print(f"[ERROR] Embedding batch {i}-{i + len(batch)}: {e}")
            errors += len(batch)
            continue

        for obs, vec in zip(batch, vectors, strict=True):
            payload = {
                "name": obs["content"][:80],
                "node_type": "Observation",
                "entity_id": obs["entity_id"],
                "project_id": obs["project_id"],
            }
            try:
                await vs.upsert(id=obs["id"], vector=vec, payload=payload)
                success += 1
            except Exception as e:
                print(f"[ERROR] Upsert {obs['id']}: {e}")
                errors += 1

        print(f"  [{i + len(batch)}/{len(missing)}] embedded")

    print(f"\n[DONE] Backfilled {success} observation vectors, {errors} errors")


if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=is_dry_run))
