"""Spreading Activation Engine for associative memory retrieval.

Implements biologically-inspired spreading activation over the knowledge graph.
Energy propagates from seed nodes through edges, decaying at each hop, with
lateral inhibition to keep only the top-K activated nodes per wave.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from claude_memory.repository import MemoryRepository

logger = logging.getLogger(__name__)


class ActivationEngine:
    """Spreading activation over the knowledge graph.

    Usage::

        engine = ActivationEngine(repo)
        seeds = engine.activate(["entity-1", "entity-2"])
        activation = engine.spread(seeds, decay=0.6, max_hops=3)
        ranked = engine.rank(candidates, vector_scores, activation, salience_scores)
    """

    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------
    # Step 1: Seed activation
    # ------------------------------------------------------------------

    def activate(
        self,
        seed_ids: list[str],
        initial_energy: float = 1.0,
    ) -> dict[str, float]:
        """Set initial activation energy on seed nodes.

        Args:
            seed_ids: Entity IDs to activate.
            initial_energy: Starting energy for each seed.

        Returns:
            Mapping ``{entity_id: energy}``.
        """
        if not seed_ids:
            return {}
        return {sid: initial_energy for sid in seed_ids}

    # ------------------------------------------------------------------
    # Step 2: BFS spread with decay + lateral inhibition
    # ------------------------------------------------------------------

    def spread(
        self,
        activation_map: dict[str, float],
        decay: float = 0.6,
        max_hops: int = 3,
        lateral_inhibition_k: int = 10,
    ) -> dict[str, float]:
        """Propagate activation energy through the graph via BFS.

        At each hop the energy reaching a neighbor is
        ``parent_energy * decay``.  Energy **accumulates** when a node
        is reachable via multiple paths.  After each hop only the top-K
        nodes (by energy) propagate further (lateral inhibition).

        Args:
            activation_map: Initial ``{id: energy}`` (output of :meth:`activate`).
            decay: Multiplicative decay per hop (0-1).
            max_hops: Maximum number of graph traversal hops.
            lateral_inhibition_k: Only top-K nodes per hop continue spreading.

        Returns:
            Full ``{entity_id: accumulated_energy}`` across all hops.
        """
        if not activation_map:
            return {}

        # Accumulated energy for every node touched
        total: dict[str, float] = dict(activation_map)

        # Frontier = nodes whose energy propagates this hop
        frontier = dict(activation_map)

        for _hop in range(max_hops):
            if not frontier:
                break

            next_frontier: dict[str, float] = {}
            frontier_ids = list(frontier.keys())

            # Fetch 1-hop neighbors for the entire frontier
            subgraph = self.repo.get_subgraph(frontier_ids, depth=1)
            edges = subgraph.get("edges", [])

            for edge in edges:
                src = edge.get("source")
                tgt = edge.get("target")
                if src is None or tgt is None:
                    continue

                # Energy flows in both directions (undirected spread)
                if src in frontier:
                    energy = frontier[src] * decay
                    next_frontier[tgt] = next_frontier.get(tgt, 0.0) + energy
                    total[tgt] = total.get(tgt, 0.0) + energy

                if tgt in frontier:
                    energy = frontier[tgt] * decay
                    next_frontier[src] = next_frontier.get(src, 0.0) + energy
                    total[src] = total.get(src, 0.0) + energy

            # Lateral inhibition: only top-K continue
            if len(next_frontier) > lateral_inhibition_k:
                sorted_items = sorted(next_frontier.items(), key=lambda x: x[1], reverse=True)
                next_frontier = dict(sorted_items[:lateral_inhibition_k])

            frontier = next_frontier

        return total

    # ------------------------------------------------------------------
    # Step 3: Composite ranking
    # ------------------------------------------------------------------

    @staticmethod
    def _recency_score(entity: dict[str, Any]) -> float:
        """Compute a 0-1 recency score from occurred_at or created_at.

        More recent entities score closer to 1.0.  Uses an exponential
        decay with a 30-day half-life.
        """
        ts_str = entity.get("occurred_at") or entity.get("created_at")
        if not ts_str:
            return 0.0
        try:
            ts = datetime.fromisoformat(str(ts_str))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - ts).total_seconds() / 86400.0
            # Exponential decay: half-life = 30 days
            return float(2.0 ** (-age_days / 30.0))
        except (ValueError, TypeError):
            return 0.0

    def rank(  # noqa: PLR0913
        self,
        candidates: list[dict[str, Any]],
        vector_scores: dict[str, float],
        activation_scores: dict[str, float],
        salience_scores: dict[str, float],
        *,
        w_sim: float = 0.4,
        w_act: float = 0.3,
        w_sal: float = 0.2,
        w_rec: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Merge scores into a composite rank and return sorted candidates.

        Formula::

            composite = similarity*w_sim + activation*w_act
                      + salience*w_sal + recency*w_rec

        Args:
            candidates: Entity dicts (must have ``"id"`` key).
            vector_scores: ``{id: similarity_score}``.
            activation_scores: ``{id: activation_energy}``.
            salience_scores: ``{id: salience_score}``.
            w_sim: Weight for similarity.
            w_act: Weight for activation.
            w_sal: Weight for salience.
            w_rec: Weight for recency.

        Returns:
            Candidates sorted by composite score descending, each enriched
            with a ``"composite_score"`` key.
        """
        if not candidates:
            return []

        # Normalize activation scores to 0-1 range
        max_act = max(activation_scores.values()) if activation_scores else 1.0
        max_act = max_act if max_act > 0 else 1.0

        scored = []
        for entity in candidates:
            eid = entity.get("id", "")
            sim = vector_scores.get(eid, 0.0)
            act = activation_scores.get(eid, 0.0) / max_act
            sal = salience_scores.get(eid, 0.0)
            rec = self._recency_score(entity)

            composite = (w_sim * sim) + (w_act * act) + (w_sal * sal) + (w_rec * rec)
            enriched = dict(entity)
            enriched["composite_score"] = round(composite, 6)
            scored.append(enriched)

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        return scored
