import os

from falkordb import FalkorDB


def probe_algos():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))
    password = os.getenv("FALKORDB_PASSWORD", "claudememory2026")

    print("Connecting to FalkorDB...")
    client = FalkorDB(host=host, port=port, password=password)
    graph = client.select_graph("claude_memory")

    # Attempt 1: Standard Algo Syntax (redisgraph-like)
    print("\n--- Testing algo.pageRank ---")
    try:
        # Standard: CALL algo.pageRank(config)
        # Or often just supported via specific libs.
        # Let's try to query it.
        # Often: CALL algo.pageRank('Entity', 'score')
        q = "CALL algo.pageRank('Entity', 'rank')"
        res = graph.query(q)
        print("✅ algo.pageRank works!")
    except Exception as e:
        print(f"❌ algo.pageRank failed: {e}")

    # Attempt 2: List all procedures again (maybe I missed something or used wrong syntax before)
    print("\n--- Listing Procedures (Standard) ---")
    try:
        res = graph.query("CALL db.procedures()")  # No WHERE clause this time
        for row in res.result_set:
            if "page" in row[0].lower() or "rank" in row[0].lower():
                print(f"Found: {row[0]} Sig: {row[1]}")
    except Exception as e:
        print(f"❌ db.procedures failed: {e}")


if __name__ == "__main__":
    probe_algos()
