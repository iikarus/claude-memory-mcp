"""Reproduction test for Librarian create_node signature mismatch (B1).

The bug: librarian.py:109 calls repo.create_node(name=..., entity_type=..., ...)
but MemoryRepository.create_node expects (label: str, properties: dict).
The TypeError is silently swallowed by the broad except on line 123.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory.clustering import Cluster, ClusteringService, StructuralGap
from claude_memory.librarian import LibrarianAgent


def _make_node(name: str, node_id: str) -> dict:
    """Helper to create a fake node dict."""
    return {
        "id": node_id,
        "name": name,
        "embedding": [0.1, 0.2, 0.3],
        "project_id": "test",
    }


@pytest.mark.asyncio
async def test_create_node_signature_produces_error_in_report():
    """run_cycle should report a GapReport error because create_node is called wrong."""
    # Setup mocks
    mock_memory = AsyncMock()
    mock_repo = MagicMock()
    mock_memory.repo = mock_repo

    mock_clustering = MagicMock(spec=ClusteringService)
    mock_clustering.min_samples = 2

    agent = LibrarianAgent(mock_memory, mock_clustering)

    # 1. get_all_nodes returns enough nodes
    nodes = [_make_node(f"n{i}", f"id{i}") for i in range(5)]
    mock_repo.get_all_nodes.return_value = nodes

    # 2. cluster_nodes returns two clusters
    cluster_a = Cluster(id=0, nodes=nodes[:3], centroid=[0.1, 0.2, 0.3], cohesion_score=0.9)
    cluster_b = Cluster(id=1, nodes=nodes[3:], centroid=[0.4, 0.5, 0.6], cohesion_score=0.8)
    mock_clustering.cluster_nodes.return_value = [cluster_a, cluster_b]

    # 3. consolidate_memories succeeds
    mock_memory.consolidate_memories.return_value = {"id": "consolidated_1"}

    # 4. get_all_edges returns empty (detect_gaps will use these)
    mock_repo.get_all_edges.return_value = []

    # 5. create_node enforces correct signature (label: str, properties: dict)
    def strict_create_node(label: str, properties: dict):
        """Enforces the real MemoryRepository.create_node signature."""
        return {"id": "gap_1", "label": label, **properties}

    mock_repo.create_node.side_effect = strict_create_node

    # 6. prune_stale succeeds
    mock_memory.prune_stale.return_value = {"deleted_count": 0}

    # Patch detect_gaps to return a gap so the create_node path is hit
    fake_gap = StructuralGap(
        cluster_a_id=0,
        cluster_b_id=1,
        similarity=0.85,
        edge_count=0,
        suggested_bridges=[],
    )
    with patch("claude_memory.librarian.detect_gaps", return_value=[fake_gap]):
        report = await agent.run_cycle()

    # After fix: create_node is called with (label, properties) correctly.
    # No GapReport errors should appear.
    gap_errors = [e for e in report["errors"] if "GapReport" in e]
    assert len(gap_errors) == 0, f"Expected zero GapReport errors after fix, got: {gap_errors}"
    # Verify create_node was actually called
    mock_repo.create_node.assert_called_once()
    call_args = mock_repo.create_node.call_args
    assert call_args[0][0] == "GapReport", f"Expected label='GapReport', got {call_args[0][0]}"
    assert isinstance(call_args[0][1], dict), "Expected properties dict as second arg"
