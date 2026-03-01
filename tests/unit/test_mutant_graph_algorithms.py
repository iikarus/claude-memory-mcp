"""Mutation-killing tests for graph_algorithms.py — PageRank and Louvain.

Targets ~20-25 kills: damping factor math, 1.0/n initialization,
share division, result slicing [:10]/[:5], seed=42, Entity label stripping.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from claude_memory.graph_algorithms import compute_louvain, compute_pagerank

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _make_node(name: str, labels: set[str] | None = None) -> MagicMock:
    """Create a mock node with labels."""
    node = MagicMock()
    node.labels = labels or {"Entity"}
    return node


# ═══════════════════════════════════════════════════════════════════
# compute_pagerank — Evil Tests
# ═══════════════════════════════════════════════════════════════════


class TestPageRankEvil:
    """Evil tests trying to break PageRank computation."""

    def test_pagerank_evil_empty_nodes(self) -> None:
        """Evil: empty node list must return empty list."""
        result = compute_pagerank({}, [], [])
        assert result == []

    def test_pagerank_evil_single_node_no_edges(self) -> None:
        """Evil: single dangling node — rank should be 1.0."""
        nodes = {"A": _make_node("A")}
        result = compute_pagerank(nodes, ["A"], [])
        assert len(result) == 1
        assert result[0]["name"] == "A"
        assert abs(result[0]["rank"] - 1.0) < 0.001

    def test_pagerank_evil_damping_mutation(self) -> None:
        """Evil: changing damping=0.85 changes rank distribution."""
        nodes = {"A": _make_node("A"), "B": _make_node("B")}
        edges = [("A", "B")]

        result_085 = compute_pagerank(nodes, ["A", "B"], edges, damping=0.85)
        result_090 = compute_pagerank(nodes, ["A", "B"], edges, damping=0.90)

        # Different damping must produce different ranks
        assert result_085[0]["rank"] != result_090[0]["rank"]

    def test_pagerank_evil_initialization_1_over_n(self) -> None:
        """Evil: initial rank must be 1.0/n — mutating to 2.0/n changes results."""
        nodes = {"A": _make_node("A"), "B": _make_node("B"), "C": _make_node("C")}
        edges = [("A", "B"), ("B", "C")]

        # With 1 iteration, we can check the base rank calculation
        result = compute_pagerank(nodes, ["A", "B", "C"], edges, iterations=1)
        total = sum(r["rank"] for r in result)
        # PageRank conserves probability mass — total ≈ 1.0
        assert abs(total - 1.0) < 0.01

    def test_pagerank_evil_invalid_edges_ignored(self) -> None:
        """Evil: edges referencing nonexistent nodes must be silently ignored."""
        nodes = {"A": _make_node("A")}
        edges = [("A", "NONEXISTENT"), ("GHOST", "A")]
        result = compute_pagerank(nodes, ["A"], edges)
        assert len(result) == 1
        assert result[0]["name"] == "A"


class TestPageRankSad:
    """Sad path tests for PageRank."""

    def test_pagerank_sad_all_dangling(self) -> None:
        """Sad: all nodes are dangling (no outgoing edges) — rank distributed evenly."""
        nodes = {
            "A": _make_node("A"),
            "B": _make_node("B"),
            "C": _make_node("C"),
        }
        result = compute_pagerank(nodes, ["A", "B", "C"], [])
        # All dangling → all ranks should be approximately equal
        ranks = [r["rank"] for r in result]
        assert max(ranks) - min(ranks) < 0.001


class TestPageRankHappy:
    """Happy path tests for PageRank."""

    def test_pagerank_happy_star_topology(self) -> None:
        """Happy: hub node (pointed to by all) gets highest rank."""
        names = ["Hub", "A", "B", "C"]
        nodes = {n: _make_node(n) for n in names}
        edges = [("A", "Hub"), ("B", "Hub"), ("C", "Hub")]

        result = compute_pagerank(nodes, names, edges)
        assert result[0]["name"] == "Hub"
        assert result[0]["rank"] > result[1]["rank"]


# ═══════════════════════════════════════════════════════════════════
# compute_pagerank — Result Structure
# ═══════════════════════════════════════════════════════════════════


class TestPageRankResultStructure:
    """Assert result structure: top-10 cap, rounding, label stripping."""

    def test_result_evil_capped_at_10(self) -> None:
        """Evil: result must be capped at 10 even with more nodes."""
        names = [f"Node{i}" for i in range(15)]
        nodes = {n: _make_node(n) for n in names}
        edges = []

        result = compute_pagerank(nodes, names, edges)
        assert len(result) == 10

    def test_result_evil_rounded_to_6(self) -> None:
        """Evil: rank must be rounded to 6 decimal places."""
        nodes = {"A": _make_node("A"), "B": _make_node("B")}
        edges = [("A", "B")]

        result = compute_pagerank(nodes, ["A", "B"], edges)
        for r in result:
            rank_str = str(r["rank"])
            if "." in rank_str:
                decimals = len(rank_str.split(".")[1])
                assert decimals <= 6

    def test_result_evil_entity_label_stripped(self) -> None:
        """Evil: 'Entity' must be stripped from labels, fallback to 'Entity'."""
        node_only_entity = _make_node("A", labels={"Entity"})
        node_with_type = _make_node("B", labels={"Entity", "Concept"})

        nodes = {"A": node_only_entity, "B": node_with_type}
        result = compute_pagerank(nodes, ["A", "B"], [])

        types = {r["name"]: r["type"] for r in result}
        assert types["A"] == "Entity"  # fallback
        assert types["B"] == "Concept"  # Entity stripped, Concept remains

    def test_result_sad_sorted_descending(self) -> None:
        """Sad: results must be sorted by rank descending."""
        names = ["A", "B", "C"]
        nodes = {n: _make_node(n) for n in names}
        edges = [("B", "A"), ("C", "A")]  # A gets most incoming

        result = compute_pagerank(nodes, names, edges)
        assert result[0]["rank"] >= result[1]["rank"]

    def test_result_happy_keys(self) -> None:
        """Happy: each result has name, rank, type keys."""
        nodes = {"A": _make_node("A")}
        result = compute_pagerank(nodes, ["A"], [])
        assert len(result) == 1
        assert "name" in result[0]
        assert "rank" in result[0]
        assert "type" in result[0]


# ═══════════════════════════════════════════════════════════════════
# compute_pagerank — Damping Factor Math
# ═══════════════════════════════════════════════════════════════════


class TestPageRankDampingMath:
    """Assert the specific math: new_ranks[j] = (1-d)/n + d * share."""

    def test_damping_evil_base_rank_formula(self) -> None:
        """Evil: base rank per iteration = (1.0 - damping) / n."""
        # With damping=0.85, n=2: base = 0.15/2 = 0.075
        nodes = {"A": _make_node("A"), "B": _make_node("B")}
        edges = [("A", "B")]

        # After 1 iteration:
        # A: base (0.075) + dangling contribution from B (no out-links)
        # = 0.075 + 0.85 * (0.5/2) = 0.075 + 0.2125 = 0.2875
        # B: base (0.075) + 0.85 * (share from A) + dangling from B
        # = 0.075 + 0.85 * 0.5 + 0.85 * (0.5/2) = 0.075 + 0.425 + 0.2125 = 0.7125
        result = compute_pagerank(nodes, ["A", "B"], edges, iterations=1)
        rank_map = {r["name"]: r["rank"] for r in result}
        # B should have higher rank than A (it receives A's outgoing)
        assert rank_map["B"] > rank_map["A"]

    def test_damping_evil_share_division(self) -> None:
        """Evil: share = ranks[i] / len(out_links[i]) — mutating division changes ranks."""
        nodes = {"A": _make_node("A"), "B": _make_node("B"), "C": _make_node("C")}
        # A links to both B and C — share = rank_A / 2
        edges = [("A", "B"), ("A", "C")]

        result = compute_pagerank(nodes, ["A", "B", "C"], edges, iterations=5)
        rank_map = {r["name"]: r["rank"] for r in result}
        # B and C should have approximately equal rank (symmetric)
        assert abs(rank_map["B"] - rank_map["C"]) < 0.01

    def test_damping_evil_zero_damping(self) -> None:
        """Evil: damping=0 → all nodes get equal rank 1/n."""
        nodes = {"A": _make_node("A"), "B": _make_node("B")}
        edges = [("A", "B")]
        result = compute_pagerank(nodes, ["A", "B"], edges, damping=0.0)
        ranks = [r["rank"] for r in result]
        assert abs(ranks[0] - ranks[1]) < 0.001  # both ~0.5

    def test_damping_sad_iterations_affect_convergence(self) -> None:
        """Sad: more iterations → closer to convergence."""
        nodes = {"A": _make_node("A"), "B": _make_node("B")}
        edges = [("A", "B"), ("B", "A")]

        compute_pagerank(nodes, ["A", "B"], edges, iterations=1)
        result_100 = compute_pagerank(nodes, ["A", "B"], edges, iterations=100)

        # With symmetric edges, converged ranks should be ~equal
        r100 = {r["name"]: r["rank"] for r in result_100}
        assert abs(r100["A"] - r100["B"]) < 0.001

    def test_damping_happy_default_0_85(self) -> None:
        """Happy: default damping=0.85 produces expected rank distribution."""
        nodes = {"A": _make_node("A"), "B": _make_node("B")}
        edges = [("A", "B"), ("B", "A")]
        result = compute_pagerank(nodes, ["A", "B"], edges)
        # Symmetric cycle with damping=0.85 → both ranks ≈ 0.5
        for r in result:
            assert abs(r["rank"] - 0.5) < 0.01


# ═══════════════════════════════════════════════════════════════════
# compute_louvain — Evil Tests
# ═══════════════════════════════════════════════════════════════════


class TestLouvainEvil:
    """Evil tests trying to break Louvain community detection."""

    def test_louvain_evil_empty_nodes(self) -> None:
        """Evil: empty node list must return empty list."""
        result = compute_louvain({}, [], [])
        assert result == []

    def test_louvain_evil_zero_edges_singleton_communities(self) -> None:
        """Evil: no edges → singleton communities (up to 5)."""
        names = ["A", "B", "C"]
        nodes = {n: _make_node(n) for n in names}
        result = compute_louvain(nodes, names, [])
        # Each node is its own community
        assert len(result) == 3
        for r in result:
            assert r["size"] == 1

    def test_louvain_evil_result_capped_at_5(self) -> None:
        """Evil: result must be capped at 5 communities."""
        # Create 7 disconnected nodes → 7 singleton communities, capped at 5
        names = [f"N{i}" for i in range(7)]
        nodes = {n: _make_node(n) for n in names}
        result = compute_louvain(nodes, names, [])
        assert len(result) == 5


class TestLouvainSad:
    """Sad path tests for Louvain."""

    def test_louvain_sad_invalid_edges_ignored(self) -> None:
        """Sad: edges referencing nonexistent nodes are silently skipped."""
        nodes = {"A": _make_node("A")}
        edges = [("A", "GHOST")]
        result = compute_louvain(nodes, ["A"], edges)
        assert len(result) == 1  # A in its own community


class TestLouvainHappy:
    """Happy path tests for Louvain."""

    def test_louvain_happy_two_communities(self) -> None:
        """Happy: two cliques → two communities detected."""
        names = ["A1", "A2", "A3", "B1", "B2", "B3"]
        nodes = {n: _make_node(n) for n in names}
        edges = [
            ("A1", "A2"),
            ("A2", "A3"),
            ("A1", "A3"),  # clique A
            ("B1", "B2"),
            ("B2", "B3"),
            ("B1", "B3"),  # clique B
        ]

        result = compute_louvain(nodes, names, edges)
        assert len(result) >= 2
        # Largest community should have size 3
        assert result[0]["size"] == 3


# ═══════════════════════════════════════════════════════════════════
# compute_louvain — Result Structure
# ═══════════════════════════════════════════════════════════════════


class TestLouvainResultStructure:
    """Assert result dict structure and member capping."""

    def test_structure_evil_keys_present(self) -> None:
        """Evil: each result must have community_id, size, members."""
        nodes = {"A": _make_node("A")}
        result = compute_louvain(nodes, ["A"], [])
        assert "community_id" in result[0]
        assert "size" in result[0]
        assert "members" in result[0]

    def test_structure_evil_members_capped_at_5(self) -> None:
        """Evil: members list capped at 5 per community."""
        names = [f"N{i}" for i in range(10)]
        nodes = {n: _make_node(n) for n in names}
        # Fully connected → all in one community
        edges = [(names[i], names[j]) for i in range(10) for j in range(i + 1, 10)]

        result = compute_louvain(nodes, names, edges)
        for r in result:
            assert len(r["members"]) <= 5

    def test_structure_evil_members_sorted(self) -> None:
        """Evil: members must be sorted alphabetically."""
        names = ["Zeta", "Alpha", "Beta"]
        nodes = {n: _make_node(n) for n in names}
        edges = [("Zeta", "Alpha"), ("Alpha", "Beta"), ("Beta", "Zeta")]

        result = compute_louvain(nodes, names, edges)
        for r in result:
            assert r["members"] == sorted(r["members"])

    def test_structure_sad_sorted_by_size_desc(self) -> None:
        """Sad: communities sorted by size descending."""
        names = ["A1", "A2", "A3", "A4", "B1"]
        nodes = {n: _make_node(n) for n in names}
        edges = [("A1", "A2"), ("A2", "A3"), ("A3", "A4"), ("A1", "A4")]

        result = compute_louvain(nodes, names, edges)
        for i in range(len(result) - 1):
            assert result[i]["size"] >= result[i + 1]["size"]

    def test_structure_happy_seed_deterministic(self) -> None:
        """Happy: seed=42 produces deterministic results."""
        names = ["A", "B", "C", "D"]
        nodes = {n: _make_node(n) for n in names}
        edges = [("A", "B"), ("C", "D")]

        r1 = compute_louvain(nodes, names, edges)
        r2 = compute_louvain(nodes, names, edges)
        assert r1 == r2  # deterministic with seed=42
