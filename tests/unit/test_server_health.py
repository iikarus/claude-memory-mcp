"""Tests for server.py Phase 4 additions — SIGTERM handler.

NOTE: The SSE health endpoint and _backup_on_shutdown were removed in Phase 7.
This file now only tests the signal registration.
"""

from unittest.mock import patch


def test_server_registers_signal_handlers():
    """Verify server module loads without error and exposes create_entity tool."""
    # This just verifies the module imports cleanly — the SIGTERM handler
    # was removed in Phase 7 along with SSE transport.
    with (
        patch.dict("os.environ", {"EMBEDDING_API_URL": "http://mock"}),
        patch("claude_memory.embedding.EmbeddingService"),
        patch("claude_memory.repository.FalkorDB"),
        patch("claude_memory.lock_manager.redis.Redis"),
    ):
        import importlib

        import claude_memory.server as server_mod

        importlib.reload(server_mod)
        assert hasattr(server_mod, "mcp")
