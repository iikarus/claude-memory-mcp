from claude_memory.context_manager import ContextManager, TokenBudget


class TestTokenBudget:
    def test_estimation(self):
        budget = TokenBudget()
        assert budget.estimate("1234") == 1  # 4 chars = 1 token
        assert budget.estimate("") == 0
        assert budget.estimate("12341234") == 2
        assert budget.estimate("1") == 1  # Verify minimum cost

    def test_check_and_consume(self):
        budget = TokenBudget(limit=10)
        text = "1234" * 5  # 20 chars = 5 tokens

        assert budget.check(text) is True
        cost = budget.consume(text)
        assert cost == 5
        assert budget.used == 5
        assert budget.remaining() == 5

        # Next 5 tokens fit exactly
        assert budget.check(text) is True
        budget.consume(text)
        assert budget.used == 10
        assert budget.remaining() == 0

        # Overflow
        assert budget.check("1") is False


class TestContextManager:
    def test_optimize_pruning(self):
        # Setup: each node ~10 tokens?
        # "Name: NodeX Type: Test" -> ~20 chars = 5 tokens
        nodes = [
            {"name": "Node1", "node_type": "Test", "description": "Desc1"},
            {"name": "Node2", "node_type": "Test", "description": "Desc2"},
            {"name": "Node3", "node_type": "Test", "description": "Desc3"},
        ]

        # Strict budget: enough for 1 full node, maybe 2 skeletons
        manager = ContextManager()
        # Mock budget to force limit
        # Let's use small limit.
        # "Name: Node1 Type: Test" -> 22 chars -> 5 tokens
        # " Description: Desc1" -> ~20 chars -> 5 tokens
        # Total per node ~10 tokens.

        optimized = manager.optimize(nodes, max_tokens=15)

        # Expect Node1 (10), Node2 (Skeleton 5), Node3 (drop)
        # Total 15.

        assert len(optimized) >= 1
        assert "description" in optimized[0]
        assert optimized[0]["description"] == "Desc1"

        if len(optimized) > 1:
            # Second node should be truncated if budget logic works as estimated
            if "description" in optimized[1]:
                assert optimized[1]["description"] == "[TRUNCATED]"

    def test_optimize_preserves_order(self):
        nodes = [{"name": f"Node{i}", "node_type": "T"} for i in range(10)]
        manager = ContextManager()
        optimized = manager.optimize(nodes, max_tokens=1000)
        assert len(optimized) == 10
        assert optimized[0]["name"] == "Node0"
        assert optimized[-1]["name"] == "Node9"
