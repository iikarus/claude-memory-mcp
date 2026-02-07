"""Context window optimization — manages token budgets for retrieval results."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TokenBudget:
    """Manages token usage against a strict budget."""

    def __init__(self, limit: int = 8000):
        """Initialize with a token budget limit."""
        self.limit = limit
        self.used = 0

    def estimate(self, text: str) -> int:
        """Heuristic token estimation (char count / 4)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def check(self, text: str) -> bool:
        """Checks if adding text would exceed the budget."""
        cost = self.estimate(text)
        return (self.used + cost) <= self.limit

    def consume(self, text: str) -> int:
        """Consumes tokens from the budget."""
        cost = self.estimate(text)
        self.used += cost
        return cost

    def remaining(self) -> int:
        """Return remaining tokens in the budget."""
        return max(0, self.limit - self.used)

    def reset(self) -> None:
        """Reset consumed tokens to zero."""
        self.used = 0


class ContextManager:
    """Govern context window usage by optimizing retrieval results."""

    def __init__(self, default_budget: int = 8000):
        """Initialize with a default token budget for context optimization."""
        self.default_budget = default_budget

    def optimize(
        self, nodes: list[dict[str, Any]], max_tokens: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Optimizes a list of nodes to fit within the token budget.

        Strategy:
        1. Prioritize by score (if available) or existing order.
        2. Include full nodes until budget is tight.
        3. If tight, include only name/type/id (skeletons).
        4. Stop when budget full.
        """
        budget_limit = max_tokens if max_tokens is not None else self.default_budget
        budget = TokenBudget(limit=budget_limit)

        # If not, we process in provided order.

        optimized_nodes: list[dict[str, Any]] = []

        for node in nodes:
            # Prepare representation for estimation
            # We estimate based on string content of values.

            # Try full include
            name = str(node.get("name", ""))
            desc = str(node.get("description", ""))
            node_type = str(node.get("node_type", "Entity"))

            # Baseline cost (Name + Type + ID overhead)
            # We estimate roughly: "Name: X, Type: Y"
            min_content = f"Name: {name} Type: {node_type}"
            min_cost = budget.estimate(min_content)

            # Check if even the skeleton fits
            if budget.remaining() < min_cost:
                # Can't even fit the skeleton. Stop.
                logger.info(
                    f"Context budget reached ({budget.used}/{budget.limit}). "
                    f"Pruning remaining {len(nodes) - len(optimized_nodes)} nodes."
                )
                break

            # Full cost includes description
            full_content = f"{min_content} Description: {desc}"

            if budget.check(full_content):
                # Fits fully
                budget.consume(full_content)
                optimized_nodes.append(node)
            else:
                # Fits only partially?
                # Strategy: Include Skeleton, drop description.
                # Clone node to avoid mutating original
                pruned_node = node.copy()
                if "description" in pruned_node:
                    # Mark as truncated so LLM knows
                    pruned_node["description"] = "[TRUNCATED]"

                # Consume the skeleton cost
                budget.consume(min_content)
                optimized_nodes.append(pruned_node)

        return optimized_nodes
