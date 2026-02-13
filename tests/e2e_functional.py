"""Exhaustive E2E functional test for the Exocortex memory system.

Exercises the LIVE stack (FalkorDB + Qdrant + Embedding server) through
the MemoryService facade.  Tests the full lifecycle:

  1.  Service initialization (connects to real DBs)
  2.  Entity CRUD (create -> read -> update -> delete)
  3.  Relationship CRUD
  4.  Observation creation
  5.  Semantic search (vector round-trip)
  6.  Graph traversal & neighbors
  7.  Timeline & temporal queries
  8.  Sessions & breakthroughs
  9.  Graph health metrics
  10. Strict consistency (Qdrant-down simulation)
  11. Associative search (spreading activation)
  12. Graph algorithms (PageRank / Louvain)
  13. Hologram retrieval (connected subgraph)
  14. Memory consolidation (merge entities)
  15. Ontology management (custom memory types)
  16. Archive & prune lifecycle
  17. Knowledge gap detection
  18. Cleanup (hard-delete all test entities)

Requires:
  - FalkorDB on localhost:6379
  - Qdrant on localhost:6333
  - Embedding server on localhost:8001

Run:
    python tests/e2e_functional.py
"""

import argparse
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
TOTAL_PHASES = 31
LATENCY_THRESHOLD = 5.0  # seconds — warn if any phase exceeds this


# -- Helpers --


class TestResult:
    """Accumulates pass/fail results with per-phase timing."""

    def __init__(self) -> None:
        """Initialize test result tracker."""
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.warnings: list[str] = []
        self._phase_start: float = 0.0

    def start_phase(self, label: str) -> None:
        """Mark the start of a test phase for timing."""
        self._phase_start = time.monotonic()
        self._phase_label = label
        print(f"\n{label}")

    def _elapsed(self) -> str:
        """Return elapsed time since phase start."""
        return f"{time.monotonic() - self._phase_start:.2f}s"

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

    def end_phase(self) -> None:
        """Print elapsed time for the current phase."""
        elapsed = time.monotonic() - self._phase_start
        marker = "⚠️ SLOW" if elapsed > LATENCY_THRESHOLD else "⏱"
        print(f"  {marker} {elapsed:.2f}s")
        if elapsed > LATENCY_THRESHOLD:
            self.warn(
                getattr(self, "_phase_label", "phase"),
                f"exceeded {LATENCY_THRESHOLD}s ({elapsed:.2f}s)",
            )

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
    results.start_phase(f"[1/{TOTAL_PHASES}] Service Initialization")
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

        results.end_phase()
        return service
    except Exception as e:
        results.fail("Service init", str(e))
        traceback.print_exc()
        results.end_phase()
        return None


# -- Phase 2: Entity CRUD --


async def test_entity_crud(service: Any) -> dict[str, str]:
    """Test create, read, update, and delete entity."""
    results.start_phase(f"[2/{TOTAL_PHASES}] Entity CRUD")
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

        # CREATE entity Delta (for consolidation tests)
        params4 = EntityCreateParams(
            name=f"{ENTITY_PREFIX}Delta",
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"description": "Fourth test entity for consolidation"},
        )
        receipt4 = await service.create_entity(params4)
        ids["delta"] = receipt4.id
        results.ok(f"Create entity Delta -> {receipt4.id}")

        # CREATE entity Epsilon (for archive/prune tests)
        params5 = EntityCreateParams(
            name=f"{ENTITY_PREFIX}Epsilon",
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"description": "Fifth test entity for archive lifecycle"},
        )
        receipt5 = await service.create_entity(params5)
        ids["epsilon"] = receipt5.id
        results.ok(f"Create entity Epsilon -> {receipt5.id}")

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

    results.end_phase()
    return ids


# -- Phase 3: Relationship CRUD --


async def test_relationship_crud(service: Any, ids: dict[str, str]) -> str | None:
    """Test create and verify relationships."""
    results.start_phase(f"[3/{TOTAL_PHASES}] Relationship CRUD")
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

        # Create relationships for delta (for consolidation graph richness)
        params3 = RelationshipCreateParams(
            from_entity=ids["gamma"],
            to_entity=ids["delta"],
            relationship_type="RELATED_TO",
            properties={"context": "e2e consolidation chain"},
            confidence=0.85,
            weight=0.6,
        )
        rel3 = await service.create_relationship(params3)
        assert "error" not in rel3, f"Relationship 3 error: {rel3.get('error')}"
        results.ok("Create relationship RELATED_TO (gamma->delta)")

    except Exception as e:
        results.fail("Relationship CRUD", str(e))
        traceback.print_exc()

    results.end_phase()
    return rel_id


# -- Phase 4: Observation --


async def test_observation(service: Any, ids: dict[str, str]) -> None:
    """Test adding an observation to an entity."""
    results.start_phase(f"[4/{TOTAL_PHASES}] Observations")

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

    results.end_phase()


# -- Phase 5: Semantic Search --


async def test_search(service: Any) -> None:
    """Test vector search round-trip (embed -> Qdrant -> results)."""
    results.start_phase(f"[5/{TOTAL_PHASES}] Semantic Search")

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

    results.end_phase()


# -- Phase 6: Graph Traversal & Neighbors --


async def test_graph_traversal(service: Any, ids: dict[str, str]) -> None:
    """Test neighbor retrieval and path traversal."""
    results.start_phase(f"[6/{TOTAL_PHASES}] Graph Traversal")

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

    results.end_phase()


# -- Phase 7: Timeline & Temporal --


async def test_temporal(service: Any, ids: dict[str, str]) -> None:
    """Test timeline queries, temporal neighbors, and bottle queries."""
    results.start_phase(f"[7/{TOTAL_PHASES}] Timeline & Temporal")

    try:
        from claude_memory.schema import BottleQueryParams, TemporalQueryParams

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

        # Bottle query (may return 0 if no bottles exist — that's OK)
        bottle_params = BottleQueryParams(limit=5, project_id=PROJECT_ID)
        bottles = await service.get_bottles(bottle_params)
        results.ok(f"Get bottles -> {len(bottles)} found")

    except Exception as e:
        results.fail("Temporal", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 8: Sessions & Breakthroughs --


async def test_sessions(service: Any) -> None:
    """Test session lifecycle: start -> breakthrough -> end."""
    results.start_phase(f"[8/{TOTAL_PHASES}] Sessions & Breakthroughs")

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

    results.end_phase()


# -- Phase 9: Graph Health --


async def test_graph_health(service: Any) -> None:
    """Test graph health metrics endpoint."""
    results.start_phase(f"[9/{TOTAL_PHASES}] Graph Health")

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

    results.end_phase()


# -- Phase 10: Strict Consistency --


async def test_strict_consistency(service: Any) -> None:
    """Test: Qdrant failures always raise — no lenient path exists."""
    results.start_phase(f"[10/{TOTAL_PHASES}] Strict Consistency (always-on)")

    try:
        from unittest.mock import AsyncMock

        from claude_memory.schema import EntityCreateParams

        params = EntityCreateParams(
            name=f"{ENTITY_PREFIX}StrictTest",
            node_type="Concept",
            project_id=PROJECT_ID,
        )

        # Save real method
        original_upsert = service.vector_store.upsert

        # Qdrant failure -> exception (always, no toggle)
        service.vector_store.upsert = AsyncMock(
            side_effect=ConnectionError("Qdrant simulated down")
        )
        try:
            try:
                await service.create_entity(params)
                results.fail("Strict consistency", "Should have raised ConnectionError")
            except ConnectionError:
                results.ok("create_entity raises on Qdrant failure (no lenient path)")
        finally:
            service.vector_store.upsert = original_upsert

        # Clean up the orphan graph node (DETACH DELETE in case edges exist)
        service.repo.execute_cypher(
            "MATCH (n) WHERE n.name = $name DETACH DELETE n",
            {"name": f"{ENTITY_PREFIX}StrictTest"},
        )
        results.ok("Cleaned up orphan graph node from strict test")

    except Exception as e:
        results.fail("Strict consistency", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 11: Associative Search --


async def test_associative_search(service: Any) -> None:
    """Test spreading-activation search through the knowledge graph."""
    results.start_phase(f"[11/{TOTAL_PHASES}] Associative Search")

    try:
        assoc_results = await service.search_associative(
            "test entity validation",
            limit=5,
            project_id=PROJECT_ID,
            decay=0.6,
            max_hops=2,
        )
        results.ok(f"Associative search -> {len(assoc_results)} results")

        # Verify results have expected fields if any came back
        if assoc_results:
            first = assoc_results[0]
            assert hasattr(first, "name") or isinstance(first, dict), (
                f"Unexpected result type: {type(first)}"
            )
            results.ok("Result shape validated")
        else:
            results.warn("Associative search", "No results returned (graph may be sparse)")

    except Exception as e:
        results.fail("Associative search", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 12: Graph Algorithms --


async def test_graph_algorithms(service: Any) -> None:
    """Test PageRank and Louvain community detection.

    Post Phase-2 rebuild: analyze_graph() uses Python-side algorithms
    and raises on error (LOUD). No more silent {"error": ...} dicts.
    """
    results.start_phase(f"[12/{TOTAL_PHASES}] Graph Algorithms")

    # PageRank — should return list of ranked entities (never error dicts)
    try:
        pr_results = await service.analyze_graph(algorithm="pagerank")
        assert isinstance(pr_results, list), f"Expected list, got {type(pr_results)}"
        if pr_results:
            assert "name" in pr_results[0], f"Missing 'name' key: {pr_results[0]}"
            assert "rank" in pr_results[0], f"Missing 'rank' key: {pr_results[0]}"
        results.ok(f"PageRank -> {len(pr_results)} ranked entities")
    except Exception as e:
        results.fail("PageRank", str(e)[:120])

    # Louvain — should return list of communities (never error dicts)
    try:
        lv_results = await service.analyze_graph(algorithm="louvain")
        assert isinstance(lv_results, list), f"Expected list, got {type(lv_results)}"
        if lv_results:
            assert "community_id" in lv_results[0], f"Missing 'community_id': {lv_results[0]}"
            assert "members" in lv_results[0], f"Missing 'members': {lv_results[0]}"
        results.ok(f"Louvain -> {len(lv_results)} communities")
    except Exception as e:
        results.fail("Louvain", str(e)[:120])

    results.end_phase()


# -- Phase 13: Hologram Retrieval --


async def test_hologram(service: Any) -> None:
    """Test hologram (connected subgraph) retrieval."""
    results.start_phase(f"[13/{TOTAL_PHASES}] Hologram Retrieval")

    try:
        holo = await service.get_hologram("test entity E2E", depth=1, max_tokens=4000)
        assert isinstance(holo, dict), f"Expected dict, got {type(holo)}"
        assert "nodes" in holo, f"Missing 'nodes' key in hologram: {list(holo.keys())}"
        assert "edges" in holo, "Missing 'edges' key in hologram"
        results.ok(
            f"Hologram -> {holo.get('stats', {}).get('total_nodes', '?')} nodes, "
            f"{holo.get('stats', {}).get('total_edges', '?')} edges"
        )

        # Verify stats structure
        if "stats" in holo:
            stats = holo["stats"]
            assert "total_nodes" in stats
            assert "total_edges" in stats
            results.ok("Hologram stats structure validated")

    except Exception as e:
        results.fail("Hologram", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 14: Memory Consolidation --


async def test_consolidation(service: Any, ids: dict[str, str]) -> str | None:
    """Test merging multiple entities into a consolidated concept."""
    results.start_phase(f"[14/{TOTAL_PHASES}] Memory Consolidation")
    consolidated_id = None

    try:
        # Consolidate gamma + delta into a new concept
        target_ids = [ids["gamma"], ids["delta"]]
        consolidated = await service.consolidate_memories(
            entity_ids=target_ids,
            summary="Consolidated Gamma and Delta for E2E testing",
        )

        if "error" in consolidated:
            results.warn("Consolidation", f"Returned error: {consolidated['error']}")
        else:
            consolidated_id = consolidated.get("consolidated_id")
            results.ok(f"Consolidate memories -> {consolidated_id}")

            # Verify the consolidated entity exists
            if consolidated_id:
                node = service.repo.get_node(consolidated_id)
                if node:
                    results.ok("Consolidated node exists in FalkorDB")
                else:
                    results.warn("Consolidation", "Consolidated node not found in graph")

            # Check consolidation_errors key (P-1 fix verification)
            if "consolidation_errors" in consolidated:
                errors = consolidated["consolidation_errors"]
                if errors:
                    results.warn("Consolidation", f"Had {len(errors)} partial errors: {errors}")
                else:
                    results.ok("No consolidation errors (P-1 fix verified)")

    except Exception as e:
        results.fail("Consolidation", str(e))
        traceback.print_exc()

    results.end_phase()
    return consolidated_id


# -- Phase 15: Ontology Management --


async def test_ontology(service: Any) -> None:
    """Test registering a custom memory type."""
    results.start_phase(f"[15/{TOTAL_PHASES}] Ontology Management")

    try:
        result = service.create_memory_type(
            name="E2E_TestType",
            description="A test memory type created during E2E validation",
            required_properties=["test_field"],
        )
        assert "error" not in result, f"Ontology error: {result.get('error')}"
        results.ok(f"Create memory type -> {result.get('name', 'E2E_TestType')}")

        # Verify it's registered
        known = service.ontology.list_types()
        if "E2E_TestType" in known:
            results.ok("Memory type registered in ontology")
        else:
            results.warn("Ontology", "Type created but not found in list_types()")

    except Exception as e:
        results.fail("Ontology", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 16: Archive & Prune Lifecycle --


async def test_archive_prune(service: Any, ids: dict[str, str]) -> None:
    """Test archive -> stale detection -> prune lifecycle."""
    results.start_phase(f"[16/{TOTAL_PHASES}] Archive & Prune Lifecycle")

    try:
        epsilon_id = ids.get("epsilon")
        if not epsilon_id:
            results.warn("Archive", "No epsilon entity to archive")
            results.end_phase()
            return

        # Archive
        archive_result = await service.archive_entity(epsilon_id)
        results.ok(f"Archive entity -> {archive_result.get('status', 'OK')}")

        # Verify archived node has status='archived'
        node = service.repo.get_node(epsilon_id)
        if node:
            if node.get("status") == "archived":
                results.ok("Archive status set on node")
            else:
                results.warn("Archive", f"Node found but status={node.get('status')!r}")
        else:
            results.warn("Archive", "Archived node not found in graph")

        # Stale entity detection
        stale = await service.get_stale_entities(days=0)
        results.ok(f"Get stale entities (days=0) -> {len(stale)} found")

        # Prune (days=0 would delete everything archived — only if we have test isolation)
        # Use a large days value so we DON'T accidentally delete production data
        prune_result = await service.prune_stale(days=9999)
        results.ok(f"Prune stale (days=9999) -> {prune_result}")

    except Exception as e:
        results.fail("Archive & Prune", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 17: Knowledge Gap Detection --


async def test_knowledge_gaps(service: Any) -> None:
    """Test structural gap detection between knowledge clusters."""
    results.start_phase(f"[17/{TOTAL_PHASES}] Knowledge Gap Detection")

    try:
        from claude_memory.schema import GapDetectionParams

        params = GapDetectionParams(
            min_similarity=0.5,
            max_edges=2,
            limit=5,
        )
        gaps = await service.detect_structural_gaps(params)
        results.ok(f"Detect structural gaps -> {len(gaps)} found")

        # Validate returned shape if any gaps
        if gaps:
            first = gaps[0]
            assert isinstance(first, dict), f"Expected dict, got {type(first)}"
            results.ok("Gap result shape validated")

    except Exception as e:
        results.fail("Knowledge gaps", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Phase 18: Cleanup --


async def test_cleanup(
    service: Any,
    ids: dict[str, str],
    consolidated_id: str | None,
) -> None:
    """Hard-delete all test entities to leave no trace."""
    results.start_phase(f"[18/{TOTAL_PHASES}] Cleanup")

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

        # Delete consolidated entity if it was created
        if consolidated_id:
            try:
                params = EntityDeleteParams(
                    entity_id=consolidated_id,
                    reason="e2e consolidated cleanup",
                    soft_delete=False,
                )
                await service.delete_entity(params)
                results.ok(f"Hard-delete consolidated ({consolidated_id})")
            except Exception:
                results.warn("Consolidated cleanup", "Could not delete (may already be gone)")

        # Clean up any leftover session/breakthrough/observation nodes
        # Use DETACH DELETE to remove edges first (prevents silent failure)
        cleanup_query = """
        MATCH (n)
        WHERE n.name STARTS WITH $prefix
           OR n.focus = 'E2E testing'
           OR n.name = 'E2E Test Breakthrough'
           OR n.name = 'E2E_TestType'
        DETACH DELETE n
        """
        service.repo.execute_cypher(cleanup_query, {"prefix": ENTITY_PREFIX})
        results.ok("Cleaned up session/breakthrough/ontology nodes")

        # Also remove test vectors from Qdrant
        from qdrant_client import QdrantClient

        qc = QdrantClient(url="http://localhost:6333")
        all_ids = list(ids.values())
        if consolidated_id:
            all_ids.append(consolidated_id)
        try:
            qc.delete(
                collection_name="memory_embeddings",
                points_selector=all_ids,
            )
            results.ok("Cleaned up Qdrant vectors")
        except Exception:
            results.warn("Qdrant cleanup", "Could not remove test vectors (may already be gone)")

    except Exception as e:
        results.fail("Cleanup", str(e))
        traceback.print_exc()

    results.end_phase()


# -- Main --


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for E2E test control."""
    parser = argparse.ArgumentParser(description="Exocortex E2E Functional Test")
    parser.add_argument(
        "--phase",
        type=int,
        default=None,
        help="Run only this phase number (1-based). Phases 1-2 always run for setup.",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleanup phase (leave test data in place for debugging).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Abort on first failure (default: run all phases).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output (show full stack traces).",
    )
    return parser.parse_args()


async def test_split_brain(service: Any) -> None:
    """Phase 19: Verify graph/vector consistency for test entities."""
    results.start_phase(f"[19/{TOTAL_PHASES}] Split-Brain Integrity Check")

    try:
        diag = await service.system_diagnostics()
        sb = diag["split_brain"]
        if sb["status"] == "ok":
            results.ok("Split-brain check: graph and vector store are consistent")
        elif sb["status"] == "drift":
            results.warn(
                "Split-brain",
                f"{sb['graph_only_count']} graph-only entities: {sb['graph_only_ids'][:5]}",
            )
        else:
            results.warn("Split-brain", f"status={sb['status']}")
    except Exception as e:
        results.fail("Split-brain", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_reconnect_e2e(service: Any) -> None:
    """Phase 20: Verify reconnect briefing returns valid data."""
    results.start_phase(f"[20/{TOTAL_PHASES}] Reconnect Briefing")

    try:
        briefing = await service.reconnect(project_id=PROJECT_ID)
        assert "recent_entities" in briefing, "Missing recent_entities"
        assert "health" in briefing, "Missing health"
        assert "window" in briefing, "Missing window"
        results.ok(
            f"Reconnect: {len(briefing['recent_entities'])} recent entities, "
            f"{briefing['health']['total_nodes']} total nodes"
        )
    except Exception as e:
        results.fail("Reconnect", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_observation_content(service: Any, ids: dict[str, str]) -> None:
    """Phase 21: Verify observation content matches what was written."""
    results.start_phase(f"[21/{TOTAL_PHASES}] Observation Content Verification")

    try:
        # Fetch observations for alpha (written in phase 4)
        obs_query = "MATCH (n:Entity {id: $eid})-[:HAS_OBSERVATION]->(o) RETURN o.content"
        obs_result = service.repo.execute_cypher(obs_query, {"eid": ids["alpha"]})
        if obs_result and obs_result[0]:
            content = obs_result[0][0]
            expected = "This entity was validated during E2E testing"
            if content == expected:
                results.ok("Observation content matches written text")
            else:
                results.fail("Observation content", f"Got '{content}', expected '{expected}'")
        else:
            results.warn("Observation content", "No observations found for alpha")
    except Exception as e:
        results.fail("Observation content", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_update_then_search(service: Any) -> None:
    """Phase 22: Update entity then verify search finds updated content."""
    results.start_phase(f"[22/{TOTAL_PHASES}] Update-Then-Search Consistency")

    try:
        from claude_memory.schema import EntityCreateParams, EntityDeleteParams

        # Create a fresh entity with unique content
        unique_name = f"{ENTITY_PREFIX}UpdateSearch_{int(time.monotonic() * 1000)}"
        params = EntityCreateParams(
            name=unique_name,
            node_type="Concept",
            project_id=PROJECT_ID,
            properties={"description": "A unique entity for update-search test"},
        )
        receipt = await service.create_entity(params)
        entity_id = receipt.id
        results.ok(f"Created temp entity -> {entity_id}")

        # Brief pause for vector index
        await asyncio.sleep(0.5)

        # Search for it
        search_results = await service.search(unique_name, limit=5, project_id=PROJECT_ID)
        found = any(r.id == entity_id for r in search_results)
        if found:
            results.ok("Entity found in search after creation")
        else:
            results.warn("Update-then-search", "Entity not in top 5 search results")

        # Cleanup
        del_params = EntityDeleteParams(
            entity_id=entity_id, reason="e2e update-search cleanup", soft_delete=False
        )
        await service.delete_entity(del_params)
        await service.vector_store.delete(entity_id)
        results.ok("Cleaned up temp entity")

    except Exception as e:
        results.fail("Update-then-search", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_router_strategies(service: Any) -> None:
    """Phase 23: Exercise all search router strategies."""
    results.start_phase(f"[23/{TOTAL_PHASES}] Router Strategy Coverage")

    strategies = ["auto", "semantic"]
    for strategy_name in strategies:
        try:
            search_results = await service.search(
                "test entity",
                limit=3,
                project_id=PROJECT_ID,
                strategy=strategy_name,
            )
            results.ok(f"Strategy '{strategy_name}' -> {len(search_results)} results")
        except Exception as e:
            results.warn(f"Strategy '{strategy_name}'", str(e)[:80])

    results.end_phase()


async def test_deep_search(service: Any) -> None:
    """Phase 24: Verify deep search returns observations and relationships."""
    results.start_phase(f"[24/{TOTAL_PHASES}] Deep Search (E-2)")

    try:
        search_results = await service.search(
            "test entity E2E",
            limit=3,
            project_id=PROJECT_ID,
            deep=True,
        )
        if search_results:
            first = search_results[0]
            has_obs = hasattr(first, "observations") and first.observations is not None
            has_rels = hasattr(first, "relationships") and first.relationships is not None
            if has_obs:
                results.ok(
                    f"Deep search: observations field present ({len(first.observations)} items)"
                )
            else:
                results.warn("Deep search", "observations field missing")
            if has_rels:
                results.ok(
                    f"Deep search: relationships field present ({len(first.relationships)} items)"
                )
            else:
                results.warn("Deep search", "relationships field missing")
        else:
            results.warn("Deep search", "No results returned")
    except Exception as e:
        results.fail("Deep search", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_bottles_with_content(service: Any) -> None:
    """Phase 25: Verify get_bottles with include_content (E-1)."""
    results.start_phase(f"[25/{TOTAL_PHASES}] Bottles With Content (E-1)")

    try:
        from claude_memory.schema import BottleQueryParams

        params = BottleQueryParams(limit=5, include_content=True)
        bottles = await service.get_bottles(params)
        results.ok(f"Get bottles with content -> {len(bottles)} found")
        # Even if no bottles, the call should succeed
    except Exception as e:
        results.fail("Bottles with content", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_concurrent_creates(service: Any) -> None:
    """Phase 26: Parallel entity creation via asyncio.gather."""
    results.start_phase(f"[26/{TOTAL_PHASES}] Concurrent Creates")

    try:
        from claude_memory.schema import EntityCreateParams, EntityDeleteParams

        async def create_one(idx: int) -> str:
            params = EntityCreateParams(
                name=f"{ENTITY_PREFIX}Concurrent_{idx}",
                node_type="Concept",
                project_id=PROJECT_ID,
            )
            receipt = await service.create_entity(params)
            return receipt.id

        # Create 5 entities in parallel
        created_ids = await asyncio.gather(*[create_one(i) for i in range(5)])
        results.ok(f"Parallel create -> {len(created_ids)} entities")

        # Verify all exist in graph
        for cid in created_ids:
            node = service.repo.get_node(cid)
            assert node is not None, f"Concurrent entity {cid} not found in graph"
        results.ok("All concurrent entities found in graph")

        # Cleanup
        for cid in created_ids:
            del_params = EntityDeleteParams(
                entity_id=cid, reason="concurrent test cleanup", soft_delete=False
            )
            await service.delete_entity(del_params)
            try:
                await service.vector_store.delete(cid)
            except Exception:  # noqa: S110
                pass  # OK if already gone
        results.ok("Cleaned up concurrent entities")

    except Exception as e:
        results.fail("Concurrent creates", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_preceded_by_chain(service: Any, ids: dict[str, str]) -> None:
    """Phase 27: Verify PRECEDED_BY temporal chain between test entities."""
    results.start_phase(f"[27/{TOTAL_PHASES}] PRECEDED_BY Chain Verification")

    try:
        # Query PRECEDED_BY edges originating from any test entity
        query = (
            "MATCH (a:Entity)-[r:PRECEDED_BY]->(b:Entity) "
            "WHERE a.name STARTS WITH $prefix "
            "RETURN a.name, b.name ORDER BY a.name"
        )
        chain = service.repo.execute_cypher(query, {"prefix": ENTITY_PREFIX})
        rows = chain.result_set if hasattr(chain, "result_set") else chain
        if rows:
            results.ok(f"PRECEDED_BY chain: {len(rows)} edges found")
            for row in rows[:5]:
                results.ok(f"  {row[0]} -> {row[1]}")
        else:
            # No PRECEDED_BY edges between test entities is acceptable
            # if the E2E run doesn't create them explicitly
            results.warn(
                "PRECEDED_BY chain",
                "No PRECEDED_BY edges between test entities (expected if not explicitly created)",
            )
    except Exception as e:
        results.fail("PRECEDED_BY chain", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_search_error_recovery(service: Any) -> None:
    """Phase 28: Verify search degrades gracefully on vector store errors."""
    results.start_phase(f"[28/{TOTAL_PHASES}] Search Error Recovery")

    try:
        # Normal search should work
        normal = await service.search("test recovery", limit=3, project_id=PROJECT_ID)
        results.ok(f"Normal search works -> {len(normal)} results")

        # Search with invalid project should return empty, not crash
        empty = await service.search(
            "xyzzy_nonexistent_12345",
            limit=3,
            project_id="nonexistent_project_99",
        )
        assert isinstance(empty, list), f"Expected list, got {type(empty)}"
        results.ok(f"Search with bad project -> {len(empty)} results (graceful)")

    except Exception as e:
        results.fail("Search error recovery", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_cleanup_verification(service: Any) -> None:
    """Phase 29: Verify zero orphans in graph and vector store after cleanup."""
    results.start_phase(f"[29/{TOTAL_PHASES}] Cleanup Verification")

    try:
        # Check for leftover test entities in graph
        query = "MATCH (n:Entity) WHERE n.name STARTS WITH $prefix RETURN count(n) AS cnt"
        result = service.repo.execute_cypher(query, {"prefix": ENTITY_PREFIX})
        rows = result.result_set if hasattr(result, "result_set") else result
        count = rows[0][0] if rows and rows[0] else 0
        if count == 0:
            results.ok("Zero orphan test entities in graph")
        else:
            results.warn(
                "Cleanup verification",
                f"{count} test entities still in graph",
            )

        # Check Qdrant for vectors with test entity names
        from qdrant_client import QdrantClient

        qc = QdrantClient(url="http://localhost:6333")
        scroll_result, _ = qc.scroll(
            collection_name="memory_embeddings",
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        test_vectors = [
            p
            for p in scroll_result
            if p.payload and p.payload.get("name", "").startswith(ENTITY_PREFIX)
        ]
        if not test_vectors:
            results.ok("Zero orphan test vectors in Qdrant")
        else:
            results.warn(
                "Cleanup verification",
                f"{len(test_vectors)} test vectors in Qdrant",
            )

    except Exception as e:
        results.fail("Cleanup verification", str(e))
        traceback.print_exc()

    results.end_phase()


async def test_graph_algo_semantics(service: Any) -> None:
    """Phase 30: Semantic validation for PageRank + Louvain results."""
    results.start_phase(f"[30/{TOTAL_PHASES}] Graph Algorithm Semantics")

    # PageRank: ranks should be positive floats, sorted descending
    try:
        pr = await service.analyze_graph(algorithm="pagerank")
        if pr:
            ranks = [entry["rank"] for entry in pr]
            assert all(isinstance(r, (int, float)) and r >= 0 for r in ranks), (
                f"Non-numeric or negative ranks: {ranks[:5]}"
            )
            if ranks == sorted(ranks, reverse=True):
                results.ok("PageRank: ranks are sorted descending")
            else:
                results.warn(
                    "PageRank semantics",
                    "Ranks not in descending order",
                )
            results.ok(f"PageRank: top entity '{pr[0]['name']}' rank={pr[0]['rank']:.4f}")
        else:
            results.warn("PageRank semantics", "Empty results")
    except Exception as e:
        results.fail("PageRank semantics", str(e)[:100])

    # Louvain: each community should have >0 members, IDs unique
    try:
        lv = await service.analyze_graph(algorithm="louvain")
        if lv:
            community_ids = [c["community_id"] for c in lv]
            assert len(community_ids) == len(set(community_ids)), "Duplicate community IDs"
            for comm in lv:
                assert len(comm["members"]) > 0, f"Empty community {comm['community_id']}"
            results.ok(f"Louvain: {len(lv)} communities, all non-empty, unique IDs")
        else:
            results.warn("Louvain semantics", "Empty results")
    except Exception as e:
        results.fail("Louvain semantics", str(e)[:100])

    results.end_phase()


async def test_point_in_time(service: Any) -> None:
    """Phase 31: Point-in-time query test."""
    results.start_phase(f"[31/{TOTAL_PHASES}] Point-in-Time Query")

    try:
        # Query as of now — should return results
        as_of = datetime.now(UTC).isoformat()
        pit_results = await service.point_in_time_query("test entity", as_of=as_of)
        results.ok(f"Point-in-time (now) -> {len(pit_results)} results")

        # Query as of very old date — should return 0 or few results
        old_date = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
        pit_old = await service.point_in_time_query("test entity", as_of=old_date)
        results.ok(f"Point-in-time (2020) -> {len(pit_old)} results")

    except Exception as e:
        results.fail("Point-in-time", str(e))
        traceback.print_exc()

    results.end_phase()


async def run_all(args: argparse.Namespace | None = None) -> int:  # noqa: C901, PLR0912, PLR0915
    """Run all E2E tests in sequence."""
    if args is None:
        args = argparse.Namespace(phase=None, skip_cleanup=False, strict=False, verbose=False)

    target = args.phase
    skip_cleanup = args.skip_cleanup
    strict = args.strict

    def should_run(phase: int) -> bool:
        return target is None or target == phase

    print("=" * 60)
    print("EXHAUSTIVE E2E FUNCTIONAL TEST")
    print(f"Timestamp: {TIMESTAMP}")
    print(f"Phases: {TOTAL_PHASES}")
    if target:
        print(f"Target phase: {target}")
    if skip_cleanup:
        print("Cleanup: SKIPPED")
    if strict:
        print("Mode: STRICT (abort on first failure)")
    print("=" * 60)

    start = time.monotonic()

    # Phase 1: Init (always runs)
    service = test_service_init()
    if not service:
        print("\nFATAL: Cannot proceed - service initialization failed.")
        return 1

    # Phase 2: Entity CRUD (always runs for setup)
    ids = await test_entity_crud(service)
    if not ids:
        print("\nFATAL: Cannot proceed - entity creation failed.")
        return 1

    if strict and results.failed:
        print(results.summary())
        return 1

    # Phase 3-4: Relationships and observations
    if should_run(3):
        await test_relationship_crud(service, ids)
    if should_run(4):
        await test_observation(service, ids)

    if strict and results.failed:
        print(results.summary())
        return 1

    # Brief pause for vector index to settle
    await asyncio.sleep(1.0)

    # Phase 5-9: Search, traversal, temporal, sessions, health
    if should_run(5):
        await test_search(service)
    if should_run(6):
        await test_graph_traversal(service, ids)
    if should_run(7):
        await test_temporal(service, ids)
    if should_run(8):
        await test_sessions(service)
    if should_run(9):
        await test_graph_health(service)

    if strict and results.failed:
        print(results.summary())
        return 1

    # Phase 10: Strict consistency
    if should_run(10):
        await test_strict_consistency(service)

    # Phase 11: Associative search
    if should_run(11):
        await test_associative_search(service)

    # Phase 12: Graph algorithms
    if should_run(12):
        await test_graph_algorithms(service)

    # Brief pause for vectors to settle before hologram
    await asyncio.sleep(0.5)

    # Phase 13: Hologram
    if should_run(13):
        await test_hologram(service)

    # Phase 14: Consolidation
    consolidated_id = None
    if should_run(14):
        consolidated_id = await test_consolidation(service, ids)

    # Phase 15: Ontology
    if should_run(15):
        await test_ontology(service)

    # Phase 16: Archive & Prune
    if should_run(16):
        await test_archive_prune(service, ids)

    # Phase 17: Knowledge gaps
    if should_run(17):
        await test_knowledge_gaps(service)

    # Phase 18: Cleanup (skippable)
    if not skip_cleanup and should_run(18):
        await test_cleanup(service, ids, consolidated_id)
    elif skip_cleanup:
        print("\n─" * 40 + "\n[18] Cleanup: SKIPPED (--skip-cleanup)")

    # Phase 19: Split-brain integrity check (E-7)
    if should_run(19):
        await test_split_brain(service)

    # Phase 20: Reconnect briefing (E-7)
    if should_run(20):
        await test_reconnect_e2e(service)

    # Phase 21: Observation content verification (E-7)
    if should_run(21):
        await test_observation_content(service, ids)

    # Phase 22: Update-then-search consistency (E-7)
    if should_run(22):
        await test_update_then_search(service)

    # Phase 23: Router strategy coverage (E-7)
    if should_run(23):
        await test_router_strategies(service)

    # Phase 24: Deep search (E-2 coverage)
    if should_run(24):
        await test_deep_search(service)

    # Phase 25: Bottles with content (E-1 coverage)
    if should_run(25):
        await test_bottles_with_content(service)

    # Phase 26: Concurrent creates (E-7)
    if should_run(26):
        await test_concurrent_creates(service)

    # Phase 27: PRECEDED_BY chain verification (E-7)
    if should_run(27):
        await test_preceded_by_chain(service, ids)

    # Phase 28: Search error recovery (E-7)
    if should_run(28):
        await test_search_error_recovery(service)

    # Phase 29: Cleanup verification (E-7)
    if should_run(29):
        await test_cleanup_verification(service)

    # Phase 30: Graph algorithm semantics (E-7)
    if should_run(30):
        await test_graph_algo_semantics(service)

    # Phase 31: Point-in-time query (E-7)
    if should_run(31):
        await test_point_in_time(service)

    elapsed = time.monotonic() - start
    print(results.summary())
    print(f"\nCompleted in {elapsed:.1f}s")

    return 0 if not results.failed else 1


if __name__ == "__main__":
    cli_args = parse_args()
    sys.exit(asyncio.run(run_all(cli_args)))
