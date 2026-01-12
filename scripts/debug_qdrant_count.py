import os

from qdrant_client import QdrantClient


def check_qdrant_count() -> None:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", 6333))
    collection_name = "memory_embeddings"

    print(f"🔌 Connecting to Qdrant at {host}:{port}...")
    try:
        client = QdrantClient(host=host, port=port)

        # Check if collection exists
        collections = client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)

        if not exists:
            print(f"⚠️ Collection '{collection_name}' not found.")
            print(f"Found collections: {[c.name for c in collections.collections]}")
            return

        count_res = client.count(collection_name=collection_name)
        print(f"\n📊 Qdrant Collection '{collection_name}' Count: {count_res.count}")

    except Exception as e:
        print(f"❌ Qdrant Check Failed: {e}")


if __name__ == "__main__":
    check_qdrant_count()
