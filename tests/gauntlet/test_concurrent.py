"""Concurrent Operations — Gauntlet R15.

Tests thread-safety of pure functions under concurrent load:
- Schema construction from multiple threads
- Router classification from multiple threads
- Ensures no data corruption or crashes under concurrency
"""

import concurrent.futures

from claude_memory.router import QueryIntent, QueryRouter
from claude_memory.schema import EntityCreateParams, SearchResult


class TestConcurrentSchemaConstruction:
    """Thread-safety of Pydantic model construction."""

    def test_concurrent_entity_creation(self):
        """T1: 1000 concurrent EntityCreateParams — no crash, no corruption."""

        def create_entity(i: int) -> EntityCreateParams:
            return EntityCreateParams(
                name=f"entity_{i}", node_type="Concept", project_id=f"proj_{i}"
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(create_entity, i) for i in range(1000)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 1000
        names = {r.name for r in results}
        assert len(names) == 1000  # all unique

    def test_concurrent_search_result_creation(self):
        """T2: 1000 concurrent SearchResult — no crash, no corruption."""

        def create_result(i: int) -> SearchResult:
            return SearchResult(
                id=f"id-{i}",
                name=f"entity_{i}",
                node_type="Concept",
                project_id="test",
                score=0.9,
                distance=0.1,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(create_result, i) for i in range(1000)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 1000


class TestConcurrentRouterClassification:
    """Thread-safety of QueryRouter.classify()."""

    def test_concurrent_classification(self):
        """T3: 1000 concurrent classifications — deterministic results."""
        router = QueryRouter()
        queries = [
            "what happened yesterday",
            "path between A and B",
            "related to entropy",
            "tell me about quantum physics",
        ]

        def classify(i: int) -> tuple[int, QueryIntent]:
            q = queries[i % len(queries)]
            return i, router.classify(q)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(classify, i) for i in range(1000)]
            results = {
                f.result()[0]: f.result()[1] for f in concurrent.futures.as_completed(futures)
            }

        # Verify determinism — same query index → same intent
        for i in range(1000):
            q = queries[i % len(queries)]
            expected = router.classify(q)
            assert results[i] == expected, f"Query {i} ({q}): {results[i]} != {expected}"


class TestConcurrentSerialization:
    """Thread-safety of JSON serialization round-trips."""

    def test_concurrent_roundtrip(self):
        """T4: 500 concurrent serialize+deserialize — no corruption."""

        def roundtrip(i: int) -> bool:
            original = EntityCreateParams(
                name=f"entity_{i}",
                node_type="Concept",
                project_id="test",
            )
            restored = EntityCreateParams.model_validate_json(original.model_dump_json())
            return restored.name == original.name

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(roundtrip, i) for i in range(500)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results)
        assert len(results) == 500
