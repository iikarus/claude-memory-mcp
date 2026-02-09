"""Backfill temporal data for existing entities.

Two-step migration:
1. Set occurred_at = created_at for entities missing occurred_at
2. Create PRECEDED_BY edges between chronologically adjacent entities per project

Usage:
    python scripts/backfill_temporal.py          # dry-run (default)
    python scripts/backfill_temporal.py --execute # actually run mutations
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _get_graph() -> Any:
    """Connect to FalkorDB and return the graph handle."""
    from falkordb import FalkorDB

    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    password = os.getenv("FALKORDB_PASSWORD")
    client = FalkorDB(host=host, port=port, password=password)
    return client.select_graph("claude_memory")


def backfill_occurred_at(graph: Any, *, dry_run: bool = True) -> int:
    """Set occurred_at = created_at for entities that lack it.

    Returns the number of entities updated.
    """
    count_query = """
    MATCH (n:Entity)
    WHERE n.occurred_at IS NULL AND n.created_at IS NOT NULL
    RETURN count(n) AS total
    """
    result = graph.query(count_query)
    total = result.result_set[0][0] if result.result_set else 0

    if total == 0:
        logger.info("  ✅ All entities already have occurred_at")
        return 0

    if dry_run:
        logger.info("  🔍 DRY RUN: %d entities would be updated", total)
        return total

    update_query = """
    MATCH (n:Entity)
    WHERE n.occurred_at IS NULL AND n.created_at IS NOT NULL
    SET n.occurred_at = n.created_at
    RETURN count(n) AS updated
    """
    result = graph.query(update_query)
    updated = result.result_set[0][0] if result.result_set else 0
    logger.info("  ✅ Updated %d entities", updated)
    return updated


def get_project_ids(graph: Any) -> list[str]:
    """Return distinct project_id values from Entity nodes."""
    query = """
    MATCH (n:Entity)
    WHERE n.project_id IS NOT NULL
    RETURN DISTINCT n.project_id AS pid
    """
    result = graph.query(query)
    return [row[0] for row in result.result_set if row]


def create_preceded_by_edges(graph: Any, *, dry_run: bool = True) -> dict[str, int]:
    """Create PRECEDED_BY edges between adjacent entities per project.

    Returns a dict mapping project_id → edges_created.
    """
    project_ids = get_project_ids(graph)
    if not project_ids:
        logger.info("  ⚠️  No projects found")
        return {}

    summary: dict[str, int] = {}

    for pid in project_ids:
        count_query = """
        MATCH (n:Entity {project_id: $pid})
        WITH n ORDER BY COALESCE(n.occurred_at, n.created_at) ASC
        WITH collect(n) AS nodes
        UNWIND range(0, size(nodes)-2) AS i
        WITH nodes[i] AS a, nodes[i+1] AS b
        WHERE NOT (a)-[:PRECEDED_BY]->(b)
        RETURN count(*) AS total
        """
        result = graph.query(count_query, {"pid": pid})
        edge_count = result.result_set[0][0] if result.result_set else 0

        if edge_count == 0:
            continue

        if dry_run:
            logger.info(
                "  🔍 DRY RUN: %d PRECEDED_BY edges would be created for project '%s'",
                edge_count,
                pid,
            )
            summary[pid] = edge_count
            continue

        create_query = """
        MATCH (n:Entity {project_id: $pid})
        WITH n ORDER BY COALESCE(n.occurred_at, n.created_at) ASC
        WITH collect(n) AS nodes
        UNWIND range(0, size(nodes)-2) AS i
        WITH nodes[i] AS a, nodes[i+1] AS b
        WHERE NOT (a)-[:PRECEDED_BY]->(b)
        CREATE (a)-[:PRECEDED_BY {created_at: $now}]->(b)
        RETURN count(*) AS edges_created
        """
        from datetime import UTC, datetime

        result = graph.query(
            create_query,
            {"pid": pid, "now": datetime.now(UTC).isoformat()},
        )
        created = result.result_set[0][0] if result.result_set else 0
        logger.info(
            "  ✅ Created %d PRECEDED_BY edges for project '%s'",
            created,
            pid,
        )
        summary[pid] = created

    return summary


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Backfill temporal data for existing entities")
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually run mutations (default is dry-run)",
    )
    args = parser.parse_args(argv)
    dry_run = not args.execute

    mode_label = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("🕐 Temporal Backfill Migration [%s]", mode_label)
    logger.info("")

    graph = _get_graph()

    # Step 1
    logger.info("Step 1: Backfill occurred_at")
    updated = backfill_occurred_at(graph, dry_run=dry_run)

    # Step 2
    logger.info("")
    logger.info("Step 2: Create PRECEDED_BY edges")
    edge_summary = create_preceded_by_edges(graph, dry_run=dry_run)

    # Summary
    total_edges = sum(edge_summary.values())
    logger.info("")
    logger.info("━━━ Summary ━━━")
    logger.info("  Entities backfilled: %d", updated)
    logger.info("  PRECEDED_BY edges:   %d", total_edges)
    logger.info("  Projects touched:    %d", len(edge_summary))

    if dry_run:
        logger.info("")
        logger.info("💡 Run with --execute to apply changes")


if __name__ == "__main__":
    main()
