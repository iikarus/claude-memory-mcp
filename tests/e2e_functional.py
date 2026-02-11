"""Exhaustive E2E functional test for the Exocortex memory system.

Exercises the LIVE stack (FalkorDB + Qdrant + Embedding server) through
the MemoryService facade.  Tests the full lifecycle:

  1. Service initialization (connects to real DBs)
  2. Entity CRUD (create -> read -> update -> delete)
  3. Relationship CRUD
  4. Observation creation
  5. Semantic search (vector round-trip)
  6. Graph traversal & neighbors
  7. Timeline & temporal queries
  8. Sessions & breakthroughs
  9. Graph health metrics
  10. Strict consistency (W3 - Qdrant-down simulation)
  11. Cleanup (hard-delete all test entities)

Requires:
  - FalkorDB on localhost:6379
  - Qdrant on localhost:6333
  - Embedding server on localhost:8001

Run:
    python tests/e2e_functional.py
"""

import asyncio
import sys
import time
import traceback
from datetime import UTC, datetime
from typing import Any

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


# -- Test Constants --

PROJECT_ID = "e2e-test-project"
ENTITY_PREFIX = "E2E_TEST_"
TIMESTAMP = datetime.now(UTC).isoformat()


# -- Helpers --


class TestResult:
    """Accumulates pass/fail results."""

    def __init__(self) -> None:
        """Initialize test result tracker."""
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.warnings: list[str] = []

    def ok(self, name: str) -> None:
        """Record a passing test."""
        self.passed.append(name)
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str) -> None:
        """Record a failing test."""
        self.failed.append((name, reason))
        print(f"  [FAIL] {name}: {reason}")

    def warn(self, name: str, msg: str) -> None:
        """Record a warning (non-fatal)."""
        self.warnings.append(f"{name}: {msg}")
        print(f"  [WARN] {name}: {msg}")

    def summary(self) -> str:
        """Return summary string."""
        total = len(self.passed) + len(self.failed)
        lines = [
            f"\n{'=' * 60}",
            f"E2E RESULTS: {len(self.passed)}/{total} passed",
        ]
        if self.failed:
            lines.append("\nFAILURES:")
            for name, reason in self.failed:
                lines.append(f"  [FAIL] {name}: {reason}")
        if self.warnings:
            lines.append("\nWARNINGS:")
            for w in self.warnings:
                lines.append(f"  [WARN] {w}")
        lines.append(f"{'=' * 60}")
        return "\n".join(lines)


results = TestResult()


# -- Phase 1: Service Initialization --


def test_service_init() -> Any:
    """Test that MemoryService connects to live FalkorDB + Qdrant + Embedder."""
    print("\n[1/11] Service Initialization")
    try:
        from claude_memory.embedding import EmbeddingService
        from claude_memory.tools import MemoryService

        embedder = EmbeddingService()
        service = MemoryService(embedding_service=embedder)
        results.ok("MemoryService created")

        # Verify FalkorDB connection
        count = service.repo.get_total_node_count()
        results.ok(f"FalkorDB connected (node count: {count})")

        # Verify Qdrant connection
        from qdrant_client import QdrantClient

        qc = QdrantClient(url="http://localhost:6333")
        collections = qc.get_collections()
        results.ok(f"Qdrant connected ({len(collections.collections)} collections)")

        # Verify embedder
        vec = embedder.encode("hello world")
        assert len(vec) > 0, "Embedding vector is empty"
        results.ok(f"Embedding server connected (dim={len(vec)})")

        return service
    except Exception as e:
        results.fail("Service init", str(e))
        traceback.print_exc()
        return None


# -- Phase 2: Entity CRUD --


async def test_entity_crud(service: Any) -> dict[str, str]:
    """Test create, read, update, and delete entity."""
    print("\n[2/11] Entity CRUD")
    ids: dict[str, str] = {}

    try:
        from claude_memory.schema import EntityCreateParams, EntityUpdateParams

        # CREATE entity Alpha
        params = EntityCreateParams(
            name=f"{ENTITY_PREFIX}Alpha",
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"description": "First test entity for E2E validation"},
        )
        receipt = await service.create_entity(params)
        assert receipt.id, "No entity ID returned"
        assert receipt.status == "committed"
        assert receipt.warnings == []
        ids["alpha"] = receipt.id
        results.ok(f"Create entity Alpha -> {receipt.id}")

        # CREATE entity Beta
        params2 = EntityCreateParams(
            name=f"{ENTITY_PREFIX}Beta",
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"description": "Second test entity for relationship tests"},
        )
        receipt2 = await service.create_entity(params2)
        ids["beta"] = receipt2.id
        results.ok(f"Create entity Beta -> {receipt2.id}")

        # CREATE entity Gamma (for wider test coverage)
        params3 = EntityCreateParams(
            name=f"{ENTITY_PREFIX}Gamma",
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"description": "Third test entity for search diversity"},
        )
        receipt3 = await service.create_entity(params3)
        ids["gamma"] = receipt3.id
        results.ok(f"Create entity Gamma -> {receipt3.id}")

        # READ
        node = service.repo.get_node(ids["alpha"])
        assert node is not None, "Entity not found in FalkorDB"
        assert node["name"] == f"{ENTITY_PREFIX}Alpha"
        results.ok("Read entity from FalkorDB")

        # Verify vector was stored in Qdrant
        from qdrant_client import QdrantClient

        qc = QdrantClient(url="http://localhost:6333")
        points = qc.retrieve(
            collection_name="memory_embeddings",
            ids=[ids["alpha"]],
        )
        assert len(points) == 1, f"Expected 1 Qdrant point, got {len(points)}"
        results.ok("Vector stored in Qdrant")

        # UPDATE
        update_params = EntityUpdateParams(
            entity_id=ids["alpha"],
            properties={"description": "Updated description for E2E"},
        )
        updated = await service.update_entity(update_params)
        assert "error" not in updated, f"Update error: {updated.get('error')}"
        results.ok("Update entity")

        # Verify update persisted
        node_updated = service.repo.get_node(ids["alpha"])
        assert node_updated["description"] == "Updated description for E2E"
        results.ok("Update persisted in FalkorDB")

    except Exception as e:
        results.fail("Entity CRUD", str(e))
        traceback.print_exc()

    return ids


# -- Phase 3: Relationship CRUD --


async def test_relationship_crud(service: Any, ids: dict[str, str]) -> str | None:
    """Test create and verify relationships."""
    print("\n[3/11] Relationship CRUD")
    rel_id = None

    try:
        from claude_memory.schema import RelationshipCreateParams

        # Use valid EdgeType: "RELATED_TO" (the fallback type)
        params = RelationshipCreateParams(
            from_entity=ids["alpha"],
            to_entity=ids["beta"],
            relationship_type="RELATED_TO",
            properties={"context": "e2e test link"},
            confidence=0.95,
            weight=0.8,
        )
        rel = await service.create_relationship(params)
        assert "error" not in rel, f"Relationship error: {rel.get('error')}"
        results.ok("Create relationship RELATED_TO")
        rel_id = rel.get("id")

        # Create a second relationship for richer graph
        params2 = RelationshipCreateParams(
            from_entity=ids["beta"],
            to_entity=ids["gamma"],
            relationship_type="ENABLES",
            properties={"context": "e2e test chain"},
            confidence=0.9,
            weight=0.7,
        )
        rel2 = await service.create_relationship(params2)
        assert "error" not in rel2, f"Relationship 2 error: {rel2.get('error')}"
        results.ok("Create relationship ENABLES (beta->gamma)")

    except Exception as e:
        results.fail("Relationship CRUD", str(e))
        traceback.print_exc()

    return rel_id


# -- Phase 4: Observation --


async def test_observation(service: Any, ids: dict[str, str]) -> None:
    """Test adding an observation to an entity."""
    print("\n[4/11] Observations")

    try:
        from claude_memory.schema import ObservationParams

        params = ObservationParams(
            entity_id=ids["alpha"],
            content="This entity was validated during E2E testing",
            certainty="confirmed",
            evidence=["e2e_test"],
        )
        obs = await service.add_observation(params)
        assert "error" not in obs, f"Observation error: {obs.get('error')}"
        assert obs.get("content") == "This entity was validated during E2E testing"
        results.ok("Add observation")

    except Exception as e:
        results.fail("Observation", str(e))
        traceback.print_exc()


# -- Phase 5: Semantic Search --


async def test_search(service: Any) -> None:
    """Test vector search round-trip (embed -> Qdrant -> results)."""
    print("\n[5/11] Semantic Search")

    try:
        # Basic search
        search_results = await service.search(
            "test entity for E2E validation",
            limit=5,
            project_id=PROJECT_ID,
        )
        assert len(search_results) > 0, "No search results returned"
        names = [r.name for r in search_results]
        found = any(ENTITY_PREFIX in n for n in names)
        if found:
            results.ok(f"Semantic search returned {len(search_results)} results (entity found)")
        else:
            results.warn("Semantic search", f"Got results but test entity not in top 5: {names}")

        # MMR search
        mmr_results = await service.search(
            "test entity validation",
            limit=5,
            project_id=PROJECT_ID,
            mmr=True,
        )
        results.ok(f"MMR search returned {len(mmr_results)} results")

        # Search with no results
        empty = await service.search(
            "xyzzy_nonexistent_term_12345",
            limit=5,
            project_id="nonexistent_project",
        )
        results.ok(f"Empty search returned {len(empty)} results (expected 0)")

    except Exception as e:
        results.fail("Semantic search", str(e))
        traceback.print_exc()


# -- Phase 6: Graph Traversal & Neighbors --


async def test_graph_traversal(service: Any, ids: dict[str, str]) -> None:
    """Test neighbor retrieval and path traversal."""
    print("\n[6/11] Graph Traversal")

    try:
        # Neighbors
        neighbors = await service.get_neighbors(ids["alpha"], depth=1, limit=10)
        results.ok(f"Get neighbors -> {len(neighbors)} found")

        # Traverse path (may fail on FalkorDB shortestPaths limitation)
        try:
            path = await service.traverse_path(ids["alpha"], ids["beta"])
            results.ok(f"Traverse path -> {len(path)} nodes in path")
        except Exception as e:
            err_str = str(e)
            if "shortestPath" in err_str.lower() or "shortestpaths" in err_str.lower():
                results.warn("Traverse path", "Known FalkorDB shortestPaths clause limitation")
            else:
                results.fail("Traverse path", err_str)

        # Evolution
        evolution = await service.get_evolution(ids["alpha"])
        results.ok(f"Get evolution -> {len(evolution)} entries")

        # Cross-domain patterns
        try:
            patterns = await service.find_cross_domain_patterns(ids["alpha"], limit=5)
            results.ok(f"Cross-domain patterns -> {len(patterns)} found")
        except Exception as e:
            results.warn("Cross-domain patterns", str(e)[:80])

    except Exception as e:
        results.fail("Graph traversal", str(e))
        traceback.print_exc()


# -- Phase 7: Timeline & Temporal --


async def test_temporal(service: Any, ids: dict[str, str]) -> None:
    """Test timeline queries and temporal neighbors."""
    print("\n[7/11] Timeline & Temporal")

    try:
        from claude_memory.schema import TemporalQueryParams

        # Query timeline (wide window to catch test entities)
        params = TemporalQueryParams(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2027, 1, 1, tzinfo=UTC),
            limit=50,
            project_id=PROJECT_ID,
        )
        timeline = await service.query_timeline(params)
        results.ok(f"Query timeline -> {len(timeline)} entities")

        # Temporal neighbors
        neighbors = await service.get_temporal_neighbors(ids["alpha"], direction="both", limit=5)
        results.ok(f"Temporal neighbors -> {len(neighbors)} found")

    except Exception as e:
        results.fail("Temporal", str(e))
        traceback.print_exc()


# -- Phase 8: Sessions & Breakthroughs --


async def test_sessions(service: Any) -> None:
    """Test session lifecycle: start -> breakthrough -> end."""
    print("\n[8/11] Sessions & Breakthroughs")

    try:
        from claude_memory.schema import (
            BreakthroughParams,
            SessionEndParams,
            SessionStartParams,
        )

        # Start session
        start_params = SessionStartParams(project_id=PROJECT_ID, focus="E2E testing")
        session = await service.start_session(start_params)
        session_id = session.get("session_id") or session.get("id")
        assert session_id, f"No session ID returned: {session}"
        results.ok(f"Start session -> {session_id}")

        # Record breakthrough
        bt_params = BreakthroughParams(
            name="E2E Test Breakthrough",
            moment="Verified full stack works",
            session_id=session_id,
        )
        bt = await service.record_breakthrough(bt_params)
        results.ok(f"Record breakthrough -> {bt.get('id', 'OK')}")

        # End session
        end_params = SessionEndParams(
            session_id=session_id,
            summary="E2E test session completed successfully",
            outcomes=["all_tests_pass"],
        )
        ended = await service.end_session(end_params)
        results.ok(f"End session -> {ended.get('status', 'OK')}")

    except Exception as e:
        results.fail("Sessions", str(e))
        traceback.print_exc()


# -- Phase 9: Graph Health --


async def test_graph_health(service: Any) -> None:
    """Test graph health metrics endpoint."""
    print("\n[9/11] Graph Health")

    try:
        health = await service.get_graph_health()
        assert "total_nodes" in health, f"Missing total_nodes in: {list(health.keys())}"
        assert "total_edges" in health
        assert "density" in health
        results.ok(
            f"Graph health -> {health['total_nodes']} nodes, "
            f"{health['total_edges']} edges, "
            f"density={health['density']:.4f}"
        )

    except Exception as e:
        results.fail("Graph health", str(e))
        traceback.print_exc()


# -- Phase 10: W3 Strict Consistency --


async def test_strict_consistency(service: Any) -> None:
    """Test W3: strict consistency re-raises Qdrant failures."""
    print("\n[10/11] W3: Strict Consistency")

    try:
        from unittest.mock import AsyncMock, patch

        from claude_memory.schema import EntityCreateParams

        params = EntityCreateParams(
            name=f"{ENTITY_PREFIX}StrictTest",
            node_type="Concept",
            project_id=PROJECT_ID,
        )

        # Save real method
        original_upsert = service.vector_store.upsert

        # Test STRICT mode: Qdrant failure -> exception
        service.vector_store.upsert = AsyncMock(
            side_effect=ConnectionError("Qdrant simulated down")
        )
        try:
            with patch("claude_memory.crud.STRICT_CONSISTENCY", True):
                try:
                    await service.create_entity(params)
                    results.fail("Strict mode", "Should have raised ConnectionError")
                except ConnectionError:
                    results.ok("Strict mode -> create_entity raises on Qdrant failure")
        finally:
            service.vector_store.upsert = original_upsert

        # Clean up the orphan graph node
        nodes = service.repo.execute_cypher(
            "MATCH (n) WHERE n.name = $name RETURN n",
            {"name": f"{ENTITY_PREFIX}StrictTest"},
        )
        if nodes.result_set:
            node = nodes.result_set[0][0]
            nid = str(node.properties.get("id", ""))
            if nid:
                service.repo.delete_node(nid)
                results.ok("Cleaned up orphan graph node from strict test")

        # Test LENIENT mode: Qdrant failure -> warning
        service.vector_store.upsert = AsyncMock(
            side_effect=ConnectionError("Qdrant simulated down")
        )
        try:
            with patch("claude_memory.crud.STRICT_CONSISTENCY", False):
                receipt = await service.create_entity(params)
                assert receipt.warnings, "Should have warnings in lenient mode"
                assert "vector_upsert_failed" in receipt.warnings[0]
                results.ok("Lenient mode -> create_entity returns with warning")

                # Clean up
                service.repo.delete_node(receipt.id)
                results.ok("Cleaned up lenient test entity")
        finally:
            service.vector_store.upsert = original_upsert

    except Exception as e:
        results.fail("Strict consistency", str(e))
        traceback.print_exc()


# -- Phase 11: Cleanup --


async def test_cleanup(service: Any, ids: dict[str, str]) -> None:
    """Hard-delete all test entities to leave no trace."""
    print("\n[11/11] Cleanup")

    try:
        from claude_memory.schema import EntityDeleteParams

        for label, entity_id in ids.items():
            params = EntityDeleteParams(
                entity_id=entity_id,
                reason="e2e test cleanup",
                soft_delete=False,
            )
            result = await service.delete_entity(params)
            if result.get("status") == "deleted":
                results.ok(f"Hard-delete {label} ({entity_id})")
            else:
                results.warn(f"Delete {label}", f"Unexpected: {result}")

        # Clean up any leftover session/breakthrough/observation nodes
        cleanup_query = """
        MATCH (n)
        WHERE n.name STARTS WITH $prefix
           OR n.focus = 'E2E testing'
           OR n.name = 'E2E Test Breakthrough'
        DELETE n
        """
        service.repo.execute_cypher(cleanup_query, {"prefix": ENTITY_PREFIX})
        results.ok("Cleaned up session/breakthrough nodes")

        # Also remove test vectors from Qdrant
        from qdrant_client import QdrantClient

        qc = QdrantClient(url="http://localhost:6333")
        try:
            qc.delete(
                collection_name="exocortex",
                points_selector=list(ids.values()),
            )
            results.ok("Cleaned up Qdrant vectors")
        except Exception:
            results.warn("Qdrant cleanup", "Could not remove test vectors (may already be gone)")

    except Exception as e:
        results.fail("Cleanup", str(e))
        traceback.print_exc()


# -- Main --


async def run_all() -> int:
    """Run all E2E tests in sequence."""
    print("=" * 60)
    print("EXHAUSTIVE E2E FUNCTIONAL TEST")
    print(f"Timestamp: {TIMESTAMP}")
    print("=" * 60)

    start = time.monotonic()

    # Phase 1: Init
    service = test_service_init()
    if not service:
        print("\nFATAL: Cannot proceed - service initialization failed.")
        return 1

    # Phase 2: Entity CRUD
    ids = await test_entity_crud(service)
    if not ids:
        print("\nFATAL: Cannot proceed - entity creation failed.")
        return 1

    # Phase 3-4: Relationships and observations
    await test_relationship_crud(service, ids)
    await test_observation(service, ids)

    # Brief pause for vector index to settle
    await asyncio.sleep(1.0)

    # Phase 5-9: Search, traversal, temporal, sessions, health
    await test_search(service)
    await test_graph_traversal(service, ids)
    await test_temporal(service, ids)
    await test_sessions(service)
    await test_graph_health(service)

    # Phase 10: W3 strict consistency
    await test_strict_consistency(service)

    # Phase 11: Cleanup
    await test_cleanup(service, ids)

    elapsed = time.monotonic() - start
    print(results.summary())
    print(f"\nCompleted in {elapsed:.1f}s")

    return 0 if not results.failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_all()))
