import os

import redis


def check_data() -> None:
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))

    print(f"🔌 Connecting to FalkorDB at {host}:{port}...")

    try:
        r = redis.Redis(host=host, port=port)
        # Check standard FalkorDB graph key. Usually 'claude_memory' based on Repository defaults.
        # We'll list keys to be sure.
        keys = r.keys("*")
        print(f"🔑 Redis Keys Found: {len(keys)}")
        for k in keys:
            print(f" - {k.decode('utf-8')}")

        # Try to execute a query if the graph module is loaded
        # Note: standard redis-py doesn't speak Cypher directly without 'graph.query'.
        # We use raw_command for simplicity to avoid installing falkordb-py if not present in this env (though docker has it).
        # Let's assume standard GRAPH.QUERY command.

        graph_key = "claude_memory"  # Default in code
        try:
            # COUNT match (n) return count(n)
            res = r.execute_command("GRAPH.QUERY", graph_key, "MATCH (n) RETURN count(n)")
            # Response format: [header, [row1]]
            count = res[1][0][0]
            print(f"\n📊 Graph '{graph_key}' Node Count: {count}")

            # COUNT Relationships
            res_edges = r.execute_command(
                "GRAPH.QUERY", graph_key, "MATCH ()-[r]->() RETURN count(r)"
            )
            count_edges = res_edges[1][0][0]
            print(f"🔗 Graph '{graph_key}' Edge Count: {count_edges}")

            # Sample 3 nodes to verify metadata
            res_sample = r.execute_command("GRAPH.QUERY", graph_key, "MATCH (n) RETURN n LIMIT 3")
            if res_sample and res_sample[1]:
                print("\n🕵️ Metadata Check (Sample Nodes):")
                for row in res_sample[1]:
                    # RedisGraph returns [ [props_list] ] structure
                    # But raw response parsing is tricky.
                    # easier to query specific properties
                    pass

            # Query properties directly for clarity
            res_props = r.execute_command(
                "GRAPH.QUERY", graph_key, "MATCH (n) RETURN n.name, n.project_id LIMIT 3"
            )
            if res_props and res_props[1]:
                for row in res_props[1]:
                    name = row[0].decode("utf-8") if isinstance(row[0], bytes) else row[0]
                    pid = row[1].decode("utf-8") if isinstance(row[1], bytes) else row[1]
                    print(f"   - Name: {name} | Project ID: {pid}")
        except Exception as e:
            print(f"\n⚠️ Could not query graph '{graph_key}': {e}")
            print("Trying to find other graphs...")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")


if __name__ == "__main__":
    check_data()
