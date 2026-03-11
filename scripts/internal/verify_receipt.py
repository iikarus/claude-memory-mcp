import asyncio

from claude_memory.interfaces import Embedder
from claude_memory.schema import EntityCreateParams
from claude_memory.tools import MemoryService


# Mock Embedder to avoid ML dependency overhead in quick verify
class MockVerifyEmbedder(Embedder):  # type: ignore
    def encode(self, text: str) -> list[float]:
        return [0.1] * 1024


async def main() -> None:
    print("🧪 Verifying Commit Receipt Logic...")

    # Initialize Service
    service = MemoryService(embedding_service=MockVerifyEmbedder())

    # Create Test Entity
    params = EntityCreateParams(
        name="Receipt Verification Test",
        node_type="Concept",
        project_id="verification",
        properties={"test_run": True},
    )

    try:
        receipt = await service.create_entity(params)

        print("\n✅ SUCCESS: Commit Receipt Received!")
        print(f"   - ID: {receipt.id}")
        print(f"   - Status: {receipt.status}")
        print(f"   - Operation Time: {receipt.operation_time_ms:.2f}ms")
        print(f"   - Total Memory Count: {receipt.total_memory_count}")
        print(f"   - Message: {receipt.message}")

        if receipt.total_memory_count > 0:
            print("\n📈 Graph count detected correctly.")
        else:
            print("\n⚠️ Graph count is 0 (Unexpected if DB has data).")

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
