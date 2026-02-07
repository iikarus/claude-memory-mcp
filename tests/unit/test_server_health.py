"""Tests for server.py Phase 4 additions: health endpoint and SIGTERM handler."""

import signal
from unittest.mock import MagicMock, patch

import pytest

from claude_memory.server import _backup_on_shutdown


class TestBackupOnShutdown:
    """Test the SIGTERM graceful shutdown handler."""

    def test_calls_backup_script(self) -> None:
        """Handler runs backup script and exits cleanly."""
        with (
            patch("subprocess.run") as mock_run,
            pytest.raises(SystemExit),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            _backup_on_shutdown(signal.SIGTERM, None)

        mock_run.assert_called_once()
        cmd_list = mock_run.call_args[0][0]
        assert "save" in cmd_list
        assert "--tag" in cmd_list
        assert "shutdown_backup" in cmd_list

    def test_exits_even_if_backup_fails(self) -> None:
        """Handler exits cleanly even if backup raises an exception."""
        with (
            patch("subprocess.run") as mock_run,
            pytest.raises(SystemExit),
        ):
            mock_run.side_effect = RuntimeError("backup broken")
            _backup_on_shutdown(signal.SIGTERM, None)


class TestHealthCheck:
    """Test the SSE health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_ok(self) -> None:
        """Health check returns status ok with transport info."""
        from claude_memory.server import _health_check

        response = await _health_check(None)
        assert response.status_code == 200
        assert b'"ok"' in response.body
