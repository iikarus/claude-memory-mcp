"""Pure-Python graph algorithms for the Exocortex memory system.

Provides PageRank (power iteration) and Louvain (greedy modularity)
implementations that operate on adjacency lists fetched via Cypher.
No external graph-algorithm library dependencies.
"""

from typing import Any


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


def _best_community_for_node(  # noqa: PLR0913
    i: int,
    adj: dict[int, dict[int, float]],
    community: list[int],
    k: list[float],
    m2: float,
    n: int,
) -> int:
    """Find the community assignment that maximises modularity gain for node i."""
    best_community = community[i]
    best_gain = 0.0
    current_c = community[i]
    ki = k[i]

    # Sum edge weights to each neighboring community
    neighbor_communities: dict[int, float] = {}
    for j, w in adj[i].items():
        c = community[j]
        neighbor_communities[c] = neighbor_communities.get(c, 0) + w

    for c, ki_in in neighbor_communities.items():
        if c == current_c:
            continue
        sigma_tot = sum(k[j] for j in range(n) if community[j] == c)
        gain = ki_in / m2 - (sigma_tot * ki) / (m2 * m2) * 2
        if gain > best_gain:
            best_gain = gain
            best_community = c

    return best_community


def compute_louvain(
    nodes: dict[str, Any],
    node_names: list[str],
    edges: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Greedy modularity-based community detection (Louvain Phase 1).

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

    name_to_idx = {name: i for i, name in enumerate(node_names)}
    # Build undirected adjacency with weights
    adj: dict[int, dict[int, float]] = {i: {} for i in range(n)}
    total_weight = 0.0
    for src, tgt in edges:
        if src in name_to_idx and tgt in name_to_idx:
            si, ti = name_to_idx[src], name_to_idx[tgt]
            adj[si][ti] = adj[si].get(ti, 0) + 1
            adj[ti][si] = adj[ti].get(si, 0) + 1
            total_weight += 1

    if total_weight == 0:
        # No edges: each node is its own community
        return [
            {"community_id": i, "size": 1, "members": [node_names[i]]} for i in range(min(n, 5))
        ]

    m2 = 2.0 * total_weight
    community = list(range(n))  # Each node starts in its own community
    k = [sum(adj[i].values()) for i in range(n)]  # Degree of each node

    # Greedy modularity optimization
    improved = True
    while improved:
        improved = False
        for i in range(n):
            best = _best_community_for_node(i, adj, community, k, m2, n)
            if best != community[i]:
                community[i] = best
                improved = True

    # Group by community
    communities: dict[int, list[str]] = {}
    for i, c in enumerate(community):
        communities.setdefault(c, []).append(node_names[i])

    # Sort by size descending, return top 5
    sorted_communities = sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)
    return [
        {
            "community_id": cid,
            "size": len(members),
            "members": members[:5],
        }
        for cid, members in sorted_communities[:5]
    ]
