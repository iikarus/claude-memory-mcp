import os
import sys

import redis
from qdrant_client import QdrantClient


def nuke_all() -> None:
    print("☢️  INITIATING NUCLEAR OPTION ☢️")
    print("This will WIPE ALL DATA from FalkorDB and Qdrant.")

    if "--force" in sys.argv:
        print("Force flag detected. Proceeding...")
    else:
        confirm = input("Are you sure? Type 'NUKE' to confirm: ")
        if confirm != "NUKE":
            print("Aborted.")
            return

    # 1. Clear FalkorDB (Redis)
    falkor_host = os.getenv("FALKORDB_HOST", "localhost")
    falkor_port = int(os.getenv("FALKORDB_PORT", 6379))
    try:
        print(f"Connecting to FalkorDB ({falkor_host})...")
        r = redis.Redis(host=falkor_host, port=falkor_port)
        r.flushall()
        print("✅ FalkorDB (Redis) FLUSHALL executed. Keys wiped.")
    except Exception as e:
        print(f"❌ FalkorDB Reset Failed: {e}")

    # 2. Clear Qdrant
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
    try:
        print(f"Connecting to Qdrant ({qdrant_host})...")
        client = QdrantClient(host=qdrant_host, port=qdrant_port)
        collections = client.get_collections()
        for c in collections.collections:
            client.delete_collection(c.name)
            print(f"✅ Deleted Qdrant Collection: {c.name}")
        print("✅ Qdrant Wiped.")
    except Exception as e:
        print(f"❌ Qdrant Reset Failed: {e}")

    print("\n✨ System is Clean. Memory is Empty. ✨")


if __name__ == "__main__":
    nuke_all()
