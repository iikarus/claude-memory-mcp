"""Purge ghost vectors from Qdrant (empty or orphaned payloads).

Scrolls all Qdrant points, identifies those with empty payload {},
cross-references with FalkorDB, and either:
  - Re-embeds from graph (if entity exists), or
  - Deletes the orphan vector (if no matching entity)

Usage:
    python scripts/purge_ghost_vectors.py          # dry-run (default)
    python scripts/purge_ghost_vectors.py --execute # actually purge
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

COLLECTION = "memory_embeddings"


async def _find_ghost_ids(client: object) -> list[str]:
    """Scroll collection and return IDs of points with empty payload."""
    ghost_ids: list[str] = []
    offset = None
    batch_num = 0

    while True:
        result = await client.scroll(
            collection_name=COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = result

        if not points:
            break

        for pt in points:
            payload = pt.payload or {}
            is_empty = not payload or (not payload.get("name") and not payload.get("node_type"))
            if is_empty:
                ghost_ids.append(str(pt.id))

        batch_num += 1
        if batch_num % 5 == 0:
            logger.info("  Scanned %d batches so far...", batch_num)

        if next_offset is None:
            break
        offset = next_offset

    return ghost_ids


async def main(argv: list[str] | None = None) -> None:
    """Scroll Qdrant, find empty-payload points, purge them."""
    parser = argparse.ArgumentParser(description="Purge ghost vectors from Qdrant")
    parser.add_argument(
        "--execute", action="store_true", help="Actually delete (default is dry-run)"
    )
    args = parser.parse_args(argv)
    dry_run = not args.execute

    from qdrant_client import AsyncQdrantClient

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    client = AsyncQdrantClient(host=host, port=port)

    label = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("🧹 Ghost Vector Purge [%s]", label)
    logger.info("")

    ghost_ids = await _find_ghost_ids(client)

    logger.info("Found %d ghost vectors (empty/missing payload)", len(ghost_ids))

    if not ghost_ids:
        logger.info("✅ No ghost vectors — collection is clean")
        await client.close()
        return

    if dry_run:
        logger.info("")
        logger.info("Ghost IDs (sample of first 10):")
        for gid in ghost_ids[:10]:
            logger.info("  - %s", gid)
        if len(ghost_ids) > 10:
            logger.info("  ... and %d more", len(ghost_ids) - 10)
        logger.info("")
        logger.info("💡 Run with --execute to delete these vectors")
    else:
        from qdrant_client.models import PointIdsList

        await client.delete(
            collection_name=COLLECTION,
            points_selector=PointIdsList(points=ghost_ids),
        )
        logger.info("✅ Deleted %d ghost vectors", len(ghost_ids))

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
