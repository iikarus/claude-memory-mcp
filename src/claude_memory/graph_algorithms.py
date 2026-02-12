"""Pure-Python graph algorithms for the Exocortex memory system.

Provides PageRank (power iteration) and Louvain (greedy modularity)
implementations that operate on adjacency lists fetched via Cypher.
No external graph-algorithm library dependencies.
"""

from typing import Any

import networkx as nx


def compute_pagerank(
    nodes: dict[str, Any],
    node_names: list[str],
    edges: list[tuple[str, str]],
    damping: float = 0.85,
    iterations: int = 20,
) -> list[dict[str, Any]]:
    """Power-iteration PageRank on an adjacency list.

    Args:
        nodes: Mapping of node name to node object (with .labels attribute).
        node_names: Ordered list of all node names.
        edges: List of (source_name, target_name) tuples.
        damping: Damping factor (default 0.85).
        iterations: Number of power-iteration rounds (default 20).

    Returns:
        Top 10 entities sorted by rank descending, each with name, rank, type.
    """
    n = len(node_names)
    if n == 0:
        return []

    name_to_idx = {name: i for i, name in enumerate(node_names)}
    ranks = [1.0 / n] * n

    # Build outgoing adjacency: source_idx -> list of target_idx
    out_links: dict[int, list[int]] = {i: [] for i in range(n)}
    for src, tgt in edges:
        if src in name_to_idx and tgt in name_to_idx:
            out_links[name_to_idx[src]].append(name_to_idx[tgt])

    for _ in range(iterations):
        new_ranks = [(1.0 - damping) / n] * n
        for i in range(n):
            if out_links[i]:
                share = ranks[i] / len(out_links[i])
                for j in out_links[i]:
                    new_ranks[j] += damping * share
            else:
                # Dangling node distributes rank evenly
                share = ranks[i] / n
                for j in range(n):
                    new_ranks[j] += damping * share
        ranks = new_ranks

    # Build sorted results
    indexed = sorted(enumerate(ranks), key=lambda x: x[1], reverse=True)
    results = []
    for idx, rank in indexed[:10]:
        name = node_names[idx]
        node = nodes[name]
        labels = set(node.labels) - {"Entity"} if hasattr(node, "labels") else set()
        results.append(
            {
                "name": name,
                "rank": round(rank, 6),
                "type": next(iter(labels)) if labels else "Entity",
            }
        )
    return results


def compute_louvain(
    nodes: dict[str, Any],
    node_names: list[str],
    edges: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Community detection using NetworkX's C-optimized Louvain.

    Args:
        nodes: Mapping of node name to node object.
        node_names: Ordered list of all node names.
        edges: List of (source_name, target_name) tuples.

    Returns:
        Top 5 communities sorted by size, each with community_id, size, members.
    """

    n = len(node_names)
    if n == 0:
        return []

    # Build NetworkX graph
    g = nx.Graph()
    g.add_nodes_from(node_names)
    valid_names = set(node_names)
    for src, tgt in edges:
        if src in valid_names and tgt in valid_names:
            g.add_edge(src, tgt)

    if g.number_of_edges() == 0:
        return [
            {"community_id": i, "size": 1, "members": [node_names[i]]} for i in range(min(n, 5))
        ]

    # NetworkX Louvain returns a list of frozensets
    communities = nx.community.louvain_communities(g, seed=42)

    # Sort by size descending, return top 5
    sorted_communities = sorted(enumerate(communities), key=lambda x: len(x[1]), reverse=True)
    return [
        {
            "community_id": cid,
            "size": len(members),
            "members": sorted(members)[:5],
        }
        for cid, members in sorted_communities[:5]
    ]
