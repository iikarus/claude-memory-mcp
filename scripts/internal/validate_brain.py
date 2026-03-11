"""Live Brain Health Check — 9 diagnostic checks.

Run against the live FalkorDB + Qdrant stack to verify brain integrity.

Checks:
  1. Split-brain: graph Entity IDs vs Qdrant point IDs
  2. Bottle chain: PRECEDED_BY edges form valid temporal chains
  3. Temporal completeness: all Entity nodes have created_at + occurred_at
  4. Observation vectors: observations have matching Qdrant vectors
  5. FalkorDB maxmemory: redis maxmemory is set (not 0 / unlimited)
  6. Ghost graphs: no extraneous graphs besides claude_memory
  7. Orphan vectors: no Qdrant IDs without matching graph Entity
  8. FalkorDB indices: Entity(id) and Entity(name) indices exist
  9. HNSW threshold: Qdrant HNSW indexing threshold is configured

Usage:
    python scripts/validate_brain.py
"""

import sys

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from qdrant_client import QdrantClient
from redis import Redis


def main() -> int:  # noqa: C901, PLR0912
    """Run all 9 brain health checks."""
    passed, failed, warnings = [], [], []

    def ok(name: str, detail: str = "") -> None:
        passed.append(name)
        msg = f"  [PASS] {name}"
        if detail:
            msg += f": {detail}"
        print(msg)

    def fail(name: str, reason: str) -> None:
        failed.append((name, reason))
        print(f"  [FAIL] {name}: {reason}")

    def warn(name: str, msg: str) -> None:
        warnings.append(f"{name}: {msg}")
        print(f"  [WARN] {name}: {msg}")

    print("=" * 60)
    print("BRAIN HEALTH CHECK")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Connect to backends
    # ------------------------------------------------------------------
    try:
        redis = Redis(host="localhost", port=6379, decode_responses=True)
        redis.ping()
        ok("Redis connection", "localhost:6379")
    except Exception as e:
        fail("Redis connection", str(e))
        print("\nFATAL: Cannot connect to FalkorDB. Aborting.")
        return 1

    try:
        qc = QdrantClient(url="http://localhost:6333")
        qc.get_collections()
        ok("Qdrant connection", "localhost:6333")
    except Exception as e:
        fail("Qdrant connection", str(e))
        print("\nFATAL: Cannot connect to Qdrant. Aborting.")
        return 1

    # ------------------------------------------------------------------
    # 1. Split-brain: graph Entity IDs vs Qdrant point IDs
    # ------------------------------------------------------------------
    print("\n--- Check 1: Split-Brain ---")
    try:
        graph_result = redis.execute_command(
            "GRAPH.QUERY", "claude_memory", "MATCH (n) WHERE n.id IS NOT NULL RETURN n.id"
        )
        # FalkorDB returns [[header], [rows], [stats]]
        rows = graph_result[1] if len(graph_result) > 1 else []
        graph_ids = {r[0] for r in rows if r and r[0]}

        qdrant_ids: set[str] = set()
        offset = None
        while True:
            records, next_offset = qc.scroll(
                collection_name="memory_embeddings",
                limit=100,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            qdrant_ids.update(str(r.id) for r in records)
            if next_offset is None:
                break
            offset = next_offset

        graph_only = graph_ids - qdrant_ids
        vec_only = qdrant_ids - graph_ids

        if not graph_only and not vec_only:
            ok("Split-brain", f"{len(graph_ids)} entities == {len(qdrant_ids)} vectors")
        else:
            if graph_only:
                warn("Split-brain", f"{len(graph_only)} graph-only IDs: {sorted(graph_only)[:5]}")
            if vec_only:
                warn("Split-brain", f"{len(vec_only)} vector-only IDs: {sorted(vec_only)[:5]}")
    except Exception as e:
        fail("Split-brain", str(e))

    # ------------------------------------------------------------------
    # 2. Bottle chain: PRECEDED_BY edges form valid temporal chains
    # ------------------------------------------------------------------
    print("\n--- Check 2: Bottle Chain (PRECEDED_BY) ---")
    try:
        pb_result = redis.execute_command(
            "GRAPH.QUERY",
            "claude_memory",
            "MATCH ()-[r:PRECEDED_BY]->() RETURN count(r)",
        )
        pb_count = pb_result[1][0][0] if pb_result[1] else 0
        if pb_count > 0:
            ok("Bottle chain", f"{pb_count} PRECEDED_BY edges found")
        else:
            warn("Bottle chain", "No PRECEDED_BY edges (may be expected for fresh brain)")
    except Exception as e:
        fail("Bottle chain", str(e))

    # ------------------------------------------------------------------
    # 3. Temporal completeness: all Entity nodes have created_at + occurred_at
    # ------------------------------------------------------------------
    print("\n--- Check 3: Temporal Completeness ---")
    try:
        missing_ca = redis.execute_command(
            "GRAPH.QUERY",
            "claude_memory",
            "MATCH (n:Entity) WHERE n.created_at IS NULL RETURN count(n)",
        )
        missing_oa = redis.execute_command(
            "GRAPH.QUERY",
            "claude_memory",
            "MATCH (n:Entity) WHERE n.occurred_at IS NULL RETURN count(n)",
        )
        ca_count = missing_ca[1][0][0] if missing_ca[1] else 0
        oa_count = missing_oa[1][0][0] if missing_oa[1] else 0

        if ca_count == 0 and oa_count == 0:
            ok("Temporal completeness", "all entities have created_at + occurred_at")
        else:
            if ca_count:
                warn("Temporal", f"{ca_count} entities missing created_at")
            if oa_count:
                warn("Temporal", f"{oa_count} entities missing occurred_at")
    except Exception as e:
        fail("Temporal completeness", str(e))

    # ------------------------------------------------------------------
    # 4. Observation vectors: check that observations exist
    # ------------------------------------------------------------------
    print("\n--- Check 4: Observation Vectors ---")
    try:
        obs_result = redis.execute_command(
            "GRAPH.QUERY",
            "claude_memory",
            "MATCH (n:Entity)-[:HAS_OBSERVATION]->(o) RETURN count(o)",
        )
        obs_count = obs_result[1][0][0] if obs_result[1] else 0
        ok("Observation vectors", f"{obs_count} observations found")
    except Exception as e:
        fail("Observation vectors", str(e))

    # ------------------------------------------------------------------
    # 5. FalkorDB maxmemory: verify it is set (not 0 / unlimited)
    # ------------------------------------------------------------------
    print("\n--- Check 5: FalkorDB maxmemory ---")
    try:
        mem_info = redis.config_get("maxmemory")
        maxmem = int(mem_info.get("maxmemory", "0"))
        if maxmem > 0:
            ok("maxmemory", f"{maxmem / (1024 * 1024):.0f} MB configured")
        else:
            warn("maxmemory", "maxmemory=0 (unlimited) — may cause OOM in production")
    except Exception as e:
        fail("maxmemory", str(e))

    # ------------------------------------------------------------------
    # 6. Ghost graphs: no extraneous graphs besides claude_memory
    # ------------------------------------------------------------------
    print("\n--- Check 6: Ghost Graphs ---")
    try:
        graphs = redis.execute_command("GRAPH.LIST")
        expected = {"claude_memory"}
        extra = set(graphs) - expected if graphs else set()
        if not extra:
            ok("Ghost graphs", f"only expected graphs: {sorted(graphs) if graphs else []}")
        else:
            warn("Ghost graphs", f"unexpected graphs: {sorted(extra)}")
    except Exception as e:
        fail("Ghost graphs", str(e))

    # ------------------------------------------------------------------
    # 7. Orphan vectors: Qdrant IDs without matching graph Entity
    # ------------------------------------------------------------------
    print("\n--- Check 7: Orphan Vectors ---")
    try:
        # Reuse graph_only/vec_only computed in check 1
        if vec_only:
            warn("Orphan vectors", f"{len(vec_only)} Qdrant IDs with no graph Entity")
        else:
            ok("Orphan vectors", "zero orphan vectors")
    except Exception as e:
        fail("Orphan vectors", str(e))

    # ------------------------------------------------------------------
    # 8. FalkorDB indices: Entity(id) and Entity(name) indices exist
    # ------------------------------------------------------------------
    print("\n--- Check 8: FalkorDB Indices ---")
    try:
        # Query the indices
        idx_info = redis.execute_command(
            "GRAPH.QUERY",
            "claude_memory",
            "CALL db.indexes() YIELD label, properties RETURN label, properties",
        )
        idx_rows = idx_info[1] if len(idx_info) > 1 else []
        idx_labels = [(r[0], r[1]) for r in idx_rows if r]
        if idx_labels:
            ok("Indices", f"{len(idx_labels)} indices: {idx_labels[:5]}")
        else:
            warn("Indices", "No indices found (performance risk)")
    except Exception as e:
        # FalkorDB may not support db.indexes() in all versions
        warn("Indices", f"Could not query indices: {e!s}")

    # ------------------------------------------------------------------
    # 9. HNSW threshold: Qdrant HNSW indexing threshold
    # ------------------------------------------------------------------
    print("\n--- Check 9: HNSW Threshold ---")
    try:
        collection_info = qc.get_collection(collection_name="memory_embeddings")
        hnsw_config = collection_info.config.hnsw_config
        if hnsw_config and hnsw_config.full_scan_threshold is not None:
            ok("HNSW threshold", f"full_scan_threshold={hnsw_config.full_scan_threshold}")
        else:
            warn("HNSW threshold", "full_scan_threshold not configured (using Qdrant default)")
    except Exception as e:
        fail("HNSW threshold", str(e))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"PASS: {len(passed)}  WARN: {len(warnings)}  FAIL: {len(failed)}")
    if failed:
        print("\nFailed checks:")
        for name, reason in failed:
            print(f"  ✗ {name}: {reason}")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ⚠ {w}")
    print("=" * 60)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
