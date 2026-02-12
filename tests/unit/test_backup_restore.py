"""Tests for backup_restore.py.

Phase 1A TDD: verifies no emoji crash risk, PYTHONUTF8 safety net,
and basic backup/restore flow via mocked subprocess.
"""

import ast
import os
import re
import sys
from unittest.mock import MagicMock, patch

# Add scripts to path to import backup_restore
sys.path.append(os.path.join(os.path.dirname(__file__), "../../scripts"))

SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backup_restore.py")
)

# ─── Phase 1A: No Emoji in Source ────────────────────────────────────

# Common emoji ranges used in the original script
_EMOJI_RE = re.compile("[\U0001f4be\U0001f4a5\u2705\u274c\u26a0\u2728\u267b\U0001f6d1]")


def test_no_emoji_in_source() -> None:
    """backup_restore.py must not contain emoji — they crash on cp1252 terminals."""
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        source = f.read()

    matches = _EMOJI_RE.findall(source)
    assert matches == [], f"Found emoji in backup_restore.py: {matches}"


def test_no_non_ascii_in_string_literals() -> None:
    """All string literals in backup_restore.py should be pure ASCII."""
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    non_ascii: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if not node.value.isascii():
                non_ascii.append(repr(node.value))

    assert non_ascii == [], f"Non-ASCII string literals found: {non_ascii}"


def test_pythonutf8_safety_net() -> None:
    """Module should set PYTHONUTF8=1 as fallback for non-UTF8 environments."""
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        source = f.read()

    assert "PYTHONUTF8" in source, "PYTHONUTF8 safety net not found in source"


def test_backup_dir_is_absolute() -> None:
    """BACKUP_DIR must be an absolute path to avoid CWD-dependent failures."""
    import backup_restore

    assert os.path.isabs(backup_restore.BACKUP_DIR), (
        f"BACKUP_DIR is relative: {backup_restore.BACKUP_DIR}"
    )


# ─── Backup Flow Tests ──────────────────────────────────────────────


class TestBackupRestore:
    """Smoke tests for backup/restore subprocess orchestration."""

    @patch("backup_restore._trigger_persistence")
    @patch("backup_restore._verify_backup")
    @patch("backup_restore.subprocess.run")
    @patch("backup_restore.os.path.exists")
    @patch("backup_restore.os.makedirs")
    def test_backup_host_mode(
        self,
        mock_makedirs: MagicMock,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        mock_verify: MagicMock,
        mock_persist: MagicMock,
    ) -> None:
        """Host mode: backup uses docker run to tar volumes."""
        import backup_restore

        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        backup_restore.backup(tag="test_host")

        assert mock_run.call_count == 2
        args_falkor = mock_run.call_args_list[0][0][0]
        assert args_falkor[0] == "docker"
        assert "alpine" in args_falkor

    @patch("backup_restore._trigger_persistence")
    @patch("backup_restore._verify_backup")
    @patch("backup_restore.subprocess.run")
    @patch("backup_restore.os.path.exists")
    @patch("backup_restore.os.makedirs")
    def test_backup_container_mode(
        self,
        mock_makedirs: MagicMock,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        mock_verify: MagicMock,
        mock_persist: MagicMock,
    ) -> None:
        """Container mode: backup uses direct tar on mounted volumes."""
        import backup_restore

        def side_effect(path: str) -> bool:
            return path in ["/mnt/falkor_data", "/mnt/qdrant_data"]

        mock_exists.side_effect = side_effect
        mock_run.return_value = MagicMock(returncode=0)

        backup_restore.backup(tag="test_container")

        assert mock_run.call_count == 2
        args_falkor = mock_run.call_args_list[0][0][0]
        assert args_falkor[0] == "tar"
