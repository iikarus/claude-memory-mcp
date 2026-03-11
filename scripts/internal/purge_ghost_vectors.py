"""Purge ghost vectors from Qdrant (empty or orphaned payloads).

Two-pass scan:
  Pass 1 — Empty-payload ghosts: points with no name/node_type in payload.
  Pass 2 — Orphan vectors: points whose ID has no matching node in FalkorDB.

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
os.environ.setdefault("FALKORDB_HOST", "localhost")
os.environ.setdefault("FALKORDB_PORT", "6379")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

COLLECTION = "memory_embeddings"
GRAPH_NAME = "claude_memory"


async def _scroll_all_ids(client: object) -> list[str]:
    """Scroll entire Qdrant collection and return all point IDs."""
    all_ids: list[str] = []
    offset = None

    while True:
        result = await client.scroll(
            collection_name=COLLECTION,
            limit=100,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        points, next_offset = result

        if not points:
            break

        for pt in points:
            all_ids.append(str(pt.id))

        if next_offset is None:
            break
        offset = next_offset

    return all_ids


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


def _get_all_graph_ids() -> set[str]:
    """Pull all node IDs from FalkorDB in a single query (Entity + Observation)."""
    from falkordb import FalkorDB

    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    db = FalkorDB(host=host, port=port)
    graph = db.select_graph(GRAPH_NAME)

    result = graph.query("MATCH (n) WHERE n.id IS NOT NULL RETURN n.id")
    return {str(row[0]) for row in result.result_set}


async def _find_orphan_ids(
    client: object,
    *,
    exclude_ids: set[str] | None = None,
    graph_ids: set[str] | None = None,
) -> list[str]:
    """Find Qdrant vectors whose IDs have no matching node in FalkorDB.

    Args:
        client: AsyncQdrantClient instance.
        exclude_ids: IDs already flagged (e.g. empty-payload ghosts) — skip these.
        graph_ids: Pre-fetched set of graph node IDs. If None, fetches from FalkorDB.

    Returns:
        List of orphan point IDs (in Qdrant but not in FalkorDB).
    """
    if exclude_ids is None:
        exclude_ids = set()

    if graph_ids is None:
        graph_ids = _get_all_graph_ids()

    logger.info("  Graph contains %d node IDs", len(graph_ids))

    # Scroll all Qdrant IDs
    all_qdrant_ids = await _scroll_all_ids(client)
    logger.info("  Qdrant contains %d vectors", len(all_qdrant_ids))

    # Set-diff: in Qdrant but NOT in graph, excluding already-flagged ghosts
    orphan_ids = [qid for qid in all_qdrant_ids if qid not in graph_ids and qid not in exclude_ids]

    return orphan_ids


def _report_ids(label: str, ids: list[str], sample_size: int = 10) -> None:
    """Print a sample of IDs for dry-run reporting."""
    if not ids:
        return
    logger.info("")
    logger.info("%s (sample of first %d):", label, min(sample_size, len(ids)))
    for gid in ids[:sample_size]:
        logger.info("  - %s", gid)
    if len(ids) > sample_size:
        logger.info("  ... and %d more", len(ids) - sample_size)


async def main(argv: list[str] | None = None) -> None:
    """Scroll Qdrant, find empty-payload ghosts + orphan vectors, purge them."""
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

    # Pass 1: Empty-payload ghosts
    logger.info("Pass 1: Scanning for empty-payload ghosts...")
    ghost_ids = await _find_ghost_ids(client)
    logger.info("  Found %d empty-payload ghosts", len(ghost_ids))

    # Pass 2: Orphan vectors (valid payload but no graph node)
    logger.info("")
    logger.info("Pass 2: Cross-referencing Qdrant ↔ FalkorDB graph...")
    orphan_ids = await _find_orphan_ids(client, exclude_ids=set(ghost_ids))
    logger.info("  Found %d orphan vectors (no graph node)", len(orphan_ids))

    # Combined
    all_purge_ids = ghost_ids + orphan_ids
    logger.info("")
    logger.info(
        "Total: %d empty-payload ghosts + %d orphan vectors = %d to purge",
        len(ghost_ids),
        len(orphan_ids),
        len(all_purge_ids),
    )

    if not all_purge_ids:
        logger.info("✅ Collection is clean — nothing to purge")
        await client.close()
        return

    if dry_run:
        _report_ids("Empty-payload ghosts", ghost_ids)
        _report_ids("Orphan vectors (no graph node)", orphan_ids)
        logger.info("")
        logger.info("💡 Run with --execute to delete these %d vectors", len(all_purge_ids))
    else:
        from qdrant_client.models import PointIdsList

        await client.delete(
            collection_name=COLLECTION,
            points_selector=PointIdsList(points=all_purge_ids),
        )
        logger.info(
            "✅ Deleted %d vectors (%d ghosts + %d orphans)",
            len(all_purge_ids),
            len(ghost_ids),
            len(orphan_ids),
        )

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
