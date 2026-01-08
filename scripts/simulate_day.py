import asyncio
import logging
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

# Import strict modules
from claude_memory.clustering import ClusteringService
from claude_memory.librarian import LibrarianAgent
from claude_memory.tools import MemoryService

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Simulation")


async def run_simulation() -> None:
    logger.info("=== STARTING SIMULATION: A DAY IN THE LIFE ===")

    # --- 1. SETUP (Morning) ---
    logger.info("\n[08:00 AM] System Startup...")

    # Mock Embedder & Repo (Mercenary Style: Logic is Real, I/O is Mocked)
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1] * 1024  # Fake 1024d vector

    # We use a real MemoryService but with a Mocked Repo to track state in-memory
    service = MemoryService(embedding_service=mock_embedder)

    # Build a simple In-Memory Graph for the Mock Repo
    in_memory_nodes: Dict[str, Any] = {}
    in_memory_edges: List[Dict[str, Any]] = []

    # Mocking Repo Methods to hit in_memory_nodes
    service.repo.create_node = MagicMock(
        side_effect=lambda label, p, e=None: _mock_create(in_memory_nodes, label, p, e)
    )
    service.repo.update_node = MagicMock(
        side_effect=lambda i, p, e=None: _mock_update(in_memory_nodes, i, p)
    )
    service.repo.get_all_nodes = MagicMock(side_effect=lambda limit: list(in_memory_nodes.values()))

    # For consolidation
    service.repo.create_edge = MagicMock(
        side_effect=lambda f, t, r, p: _mock_edge(in_memory_edges, f, t, r, p)
    )

    # --- 2. WORK (Noon) ---
    logger.info("\n[10:00 AM] User starts 'Project Tesseract'...")

    # User Action 1: Create Project Entity
    # Use direct dict for params to bypass pydantic validation complexity in script for now,
    # or better: use real params if importable.
    # Let's use the service methods which take Pydantic models.
    from claude_memory.schema import EntityCreateParams

    p1 = EntityCreateParams(
        name="Project Tesseract",
        node_type="Project",
        project_id="tesseract",
        properties={"description": "A new AI memory system"},
    )
    res = await service.create_entity(p1)
    logger.info(f" -> Created Project: {res['name']} (ID: {res['id']})")

    # User Action 2: Add Observations (Fragments)
    logger.info("\n[01:00 PM] User adds scattered notes...")

    obs_inputs = [
        "Tesseract needs a vector database.",
        "We should use FalkorDB for the graph backend.",
        "The architecture requires strict dependency injection.",
        "Memory nodes should be clustered by semantic similarity.",
    ]

    for content in obs_inputs:
        # We cheat slightly and create them as Entities for the Librarian to find easily
        # (Librarian clusters Entities currently)
        # In reality, Observations are attached to entities, but let's make them 'Note' entities.
        p_note = EntityCreateParams(
            name=f"Note: {content[:20]}...",
            node_type="Entity",
            project_id="tesseract",
            properties={"content": content, "description": content},
        )
        # Mock embedding variation to simulate clustering
        # We manually set embedding in the mock call if we could, but here we just rely on the fixed mock.
        # To make clustering work, we need the Mock Repo to return different embeddings?
        # The ClusteringService uses what's in 'embedding' field.

        # Let's inject a "fake" embedding into the property storage for the Librarian to see
        # The service.create_entity logic calls embedder.encode -> repo.create_node(..., embedding)
        # Our _mock_create saves it. All get [0.1]*1024.
        # DBSCAN with eps=0.5 will group them all representing a "tight cluster".

        await service.create_entity(p_note)
        logger.info(f" -> Added Note: '{content[:30]}...'")

    logger.info(f"\nCurrent Graph Status: {len(in_memory_nodes)} nodes.")

    # --- 3. MAINTENANCE (Night) ---
    logger.info("\n[02:00 AM] The Librarian wakes up...")

    clustering = ClusteringService(eps=0.5, min_samples=3)
    librarian = LibrarianAgent(service, clustering)

    # Run the Cycle
    report = await librarian.run_cycle()

    logger.info(f" -> Librarian Report: {report}")

    if report["clusters_found"] > 0:
        logger.info(" -> \U0001F4DA CLUSTER DETECTED!")
        logger.info(" -> \U0001F9EA SYNTHESIZING CONCEPTS...")
        logger.info(f" -> Concepts Created: {report['consolidations_created']}")

        # Verify the new Concept exists
        concepts = [n for n in in_memory_nodes.values() if n.get("node_type") == "Concept"]
        if concepts:
            c = concepts[0]
            logger.info(f"\n[NEW ENTITY] {c.get('name')}")
            logger.info(f"Description: {c.get('description')}")

    # --- 4. RETRIEVAL (Next Morning) ---
    logger.info("\n[09:00 AM Next Day] User queries the system...")

    # Simulating retrieval of the new concept
    # (Mocking search isn't set up, but we can inspect the graph)

    total_active = len([n for n in in_memory_nodes.values() if n.get("status") != "archived"])
    total_archived = len([n for n in in_memory_nodes.values() if n.get("status") == "archived"])

    logger.info(f"Active Nodes: {total_active}")
    logger.info(f"Archived Nodes: {total_archived} (Original notes hidden)")

    logger.info("\n=== SIMULATION COMPLETE ===")


# --- Internal Mocks ---


def _mock_create(
    store: Dict[str, Any],
    label: str,
    props: Dict[str, Any],
    embedding: Optional[List[float]] = None,
) -> Dict[str, Any]:
    import uuid

    pid = props.get("id") or str(uuid.uuid4())
    props["id"] = pid
    props["label"] = label
    props["embedding"] = embedding or [0.1] * 1024  # Store embedding for fetch
    store[pid] = props
    return props


def _mock_update(
    store: Dict[str, Any], pid: str, props: Dict[str, Any], embedding: Optional[List[float]] = None
) -> Optional[Dict[str, Any]]:
    if pid in store:
        store[pid].update(props)
        if embedding:
            store[pid]["embedding"] = embedding
        return store[pid]  # type: ignore
    return None


def _mock_edge(
    edge_store: List[Dict[str, Any]], f: str, t: str, r: str, p: Dict[str, Any]
) -> Dict[str, Any]:
    edge_store.append({"from": f, "to": t, "type": r, "props": p})
    return p


if __name__ == "__main__":
    asyncio.run(run_simulation())
