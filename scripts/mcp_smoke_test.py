"""MCP Smoke Test — verify 5 core tool pipelines against Docker stack."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


async def smoke() -> None:
    from claude_memory.embedding import EmbeddingService
    from claude_memory.schema import BottleQueryParams
    from claude_memory.tools import MemoryService

    embedder = EmbeddingService()
    svc = MemoryService(embedding_service=embedder)
    print("=== MCP SMOKE TEST ===")
    passed = 0
    failed = 0

    # 1. get_bottles
    try:
        params = BottleQueryParams(limit=3)
        bottles = await svc.get_bottles(params)
        print(f"[PASS] get_bottles() -> {len(bottles)} bottles")
        passed += 1
    except Exception as e:
        print(f"[FAIL] get_bottles: {e}")
        failed += 1

    # 2. search_memory
    try:
        results = await svc.search("test query", limit=3)
        print(f"[PASS] search_memory -> {len(results)} results")
        passed += 1
    except Exception as e:
        print(f"[FAIL] search_memory: {e}")
        failed += 1

    # 3. graph_health
    try:
        health = await svc.get_graph_health()
        nodes = health["total_nodes"]
        edges = health["total_edges"]
        print(f"[PASS] graph_health() -> {nodes} nodes, {edges} edges")
        passed += 1
    except Exception as e:
        print(f"[FAIL] graph_health: {e}")
        failed += 1

    # 4. system_diagnostics
    try:
        diag = await svc.system_diagnostics()
        print(f"[PASS] system_diagnostics() -> keys: {list(diag.keys())}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] system_diagnostics: {e}")
        failed += 1

    # 5. reconnect
    try:
        briefing = await svc.reconnect()
        total = briefing["health"]["total_nodes"]
        window = briefing["window"]
        print(f"[PASS] reconnect() -> {total} nodes, window={window}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] reconnect: {e}")
        failed += 1

    print(f"\n=== {passed}/{passed + failed} PASSED ===")


if __name__ == "__main__":
    asyncio.run(smoke())
