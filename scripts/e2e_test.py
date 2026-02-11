"""End-to-end integration test against the live Exocortex stack.

Exercises the full MemoryService lifecycle:
  1. Create entities
  2. Add observations
  3. Create relationships
  4. Vector search
  5. Start / end session
  6. Graph traversal (get_neighbors)
  7. Timeline query
  8. Delete entity
  9. Verify deletion

Requires: FalkorDB, Qdrant, and Embedding server all running.
Usage:  python scripts/e2e_test.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from claude_memory.embedding import EmbeddingService
from claude_memory.schema import (
    EntityCreateParams,
    EntityDeleteParams,
    ObservationParams,
    RelationshipCreateParams,
    SessionEndParams,
    SessionStartParams,
    TemporalQueryParams,
)
from claude_memory.tools import MemoryService

# ── Test configuration ──────────────────────────────────────────────
TEST_PROJECT = "e2e_test_project"
E2E_PREFIX = "E2E_TEST_"


def _banner(msg: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {msg}")
    print(f"{'─' * 60}")


async def run_e2e() -> bool:
    """Run the full end-to-end test suite. Returns True if all pass."""
    passed = 0
    failed = 0
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        status = "✅ PASS" if condition else "❌ FAIL"
        print(f"  {status}  {name}{f' — {detail}' if detail else ''}")
        results.append((name, condition, detail))
        if condition:
            passed += 1
        else:
            failed += 1

    # ── Setup ────────────────────────────────────────────────────────
    _banner("SETUP: Connecting to live services")
    try:
        embedder = EmbeddingService()
        svc = MemoryService(embedding_service=embedder)
        print("  Connected to FalkorDB, Qdrant, Embedding server")
    except Exception as exc:
        print(f"  ❌ FATAL: Cannot connect to services: {exc}")
        return False

    # ── 1. Create Entities ───────────────────────────────────────────
    _banner("1. CREATE ENTITIES")

    entity_a = await svc.create_entity(
        EntityCreateParams(
            name=f"{E2E_PREFIX}Alpha_Concept",
            node_type="Concept",
            project_id=TEST_PROJECT,
        )
    )
    check(
        "Create entity A",
        entity_a is not None and hasattr(entity_a, "id"),
        f"id={getattr(entity_a, 'id', '?')}",
    )
    entity_a_id = entity_a.id

    entity_b = await svc.create_entity(
        EntityCreateParams(
            name=f"{E2E_PREFIX}Beta_Concept",
            node_type="Concept",
            project_id=TEST_PROJECT,
        )
    )
    check(
        "Create entity B",
        entity_b is not None and hasattr(entity_b, "id"),
        f"id={getattr(entity_b, 'id', '?')}",
    )
    entity_b_id = entity_b.id

    # ── 2. Add Observations ──────────────────────────────────────────
    _banner("2. ADD OBSERVATIONS")

    obs = await svc.add_observation(
        ObservationParams(
            entity_id=entity_a_id,
            content="Alpha is fundamental to understanding graph traversal algorithms.",
        )
    )
    check(
        "Add observation",
        obs is not None,
        f"obs={obs.get('id', '?') if isinstance(obs, dict) else '?'}",
    )

    # ── 3. Create Relationship ───────────────────────────────────────
    _banner("3. CREATE RELATIONSHIP")

    rel = await svc.create_relationship(
        RelationshipCreateParams(
            from_entity=entity_a_id,
            to_entity=entity_b_id,
            relationship_type="RELATED_TO",
        )
    )
    check("Create relationship A→B", rel is not None, f"rel={rel}")

    # ── 4. Vector Search ─────────────────────────────────────────────
    _banner("4. VECTOR SEARCH")

    # Small delay for indexing
    await asyncio.sleep(0.5)
    search_results = await svc.search(
        "graph traversal algorithms",
        limit=5,
        project_id=TEST_PROJECT,
    )
    check(
        "Vector search returns results",
        isinstance(search_results, list) and len(search_results) > 0,
        f"count={len(search_results) if isinstance(search_results, list) else 0}",
    )

    # Check that our entity is in results
    if isinstance(search_results, list) and len(search_results) > 0:
        found_alpha = any(
            E2E_PREFIX in str(r.get("name", ""))
            if isinstance(r, dict)
            else E2E_PREFIX in str(getattr(r, "name", ""))
            for r in search_results
        )
        check("Search finds our test entity", found_alpha, "Alpha found in results")

    # ── 5. Session Lifecycle ─────────────────────────────────────────
    _banner("5. SESSION LIFECYCLE")

    session = await svc.start_session(
        SessionStartParams(
            project_id=TEST_PROJECT,
            focus="E2E testing session",
        )
    )
    check(
        "Start session",
        session is not None and "id" in session,
        f"session_id={session.get('id', '?')}",
    )
    session_id = session.get("id", "unknown")

    ended = await svc.end_session(
        SessionEndParams(
            session_id=session_id,
            summary="E2E test session completed successfully",
        )
    )
    check(
        "End session",
        ended is not None and ended.get("status") == "closed",
        f"status={ended.get('status', '?')}",
    )

    # ── 6. Graph Traversal (Neighbors) ───────────────────────────────
    _banner("6. GRAPH TRAVERSAL")

    neighbors = await svc.get_neighbors(entity_a_id, depth=1, limit=10)
    check(
        "Get neighbors of entity A",
        isinstance(neighbors, list),
        f"count={len(neighbors) if isinstance(neighbors, list) else 'N/A'}",
    )
    if isinstance(neighbors, list) and len(neighbors) > 0:
        found_beta = any(
            E2E_PREFIX + "Beta" in str(n.get("name", "")) for n in neighbors if isinstance(n, dict)
        )
        check("Neighbor includes Beta", found_beta)

    # ── 7. Timeline Query ────────────────────────────────────────────
    _banner("7. TIMELINE QUERY")

    from datetime import UTC, datetime, timedelta

    timeline = await svc.query_timeline(
        TemporalQueryParams(
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
            limit=10,
            project_id=TEST_PROJECT,
        )
    )
    check(
        "Timeline query",
        isinstance(timeline, list),
        f"count={len(timeline) if isinstance(timeline, list) else 'N/A'}",
    )

    # ── 8. Delete Entity ─────────────────────────────────────────────
    _banner("8. CLEANUP — DELETE TEST ENTITIES")

    del_a = await svc.delete_entity(EntityDeleteParams(entity_id=entity_a_id, reason="e2e cleanup"))
    check("Delete entity A", del_a is not None, f"result={del_a}")

    del_b = await svc.delete_entity(EntityDeleteParams(entity_id=entity_b_id, reason="e2e cleanup"))
    check("Delete entity B", del_b is not None, f"result={del_b}")

    # ── 9. Verify Deletion ───────────────────────────────────────────
    _banner("9. VERIFY DELETION")

    post_search = await svc.search(
        E2E_PREFIX + "Alpha",
        limit=5,
        project_id=TEST_PROJECT,
    )
    alpha_still_exists = any(
        E2E_PREFIX + "Alpha" in str(r.get("name", ""))
        if isinstance(r, dict)
        else E2E_PREFIX + "Alpha" in str(getattr(r, "name", ""))
        for r in (post_search or [])
    )
    check("Entity A no longer in search", not alpha_still_exists)

    # ── Summary ──────────────────────────────────────────────────────
    _banner(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}")

    return failed == 0


if __name__ == "__main__":
    start = time.monotonic()
    success = asyncio.run(run_e2e())
    elapsed = time.monotonic() - start
    print(f"\nCompleted in {elapsed:.1f}s")
    sys.exit(0 if success else 1)
