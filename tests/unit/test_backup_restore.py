import os
import sys
from unittest.mock import MagicMock, patch

# Add scripts to path to import backup_restore
sys.path.append(os.path.join(os.path.dirname(__file__), "../../scripts"))
import backup_restore


class TestBackupRestore:
    @patch("backup_restore.subprocess.run")
    @patch("backup_restore.os.path.exists")
    @patch("backup_restore.os.makedirs")
    def test_backup_host_mode(self, mock_makedirs, mock_exists, mock_run):
        # Setup: Host mode (paths don't exist in /mnt)
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        # Execute
        backup_restore.backup(tag="test_host")

        # Verify: Should use docker run calls
        # We expect 2 subprocess calls (Falkor + Qdrant)
        assert mock_run.call_count == 2

        args_falkor = mock_run.call_args_list[0][0][0]
        assert args_falkor[0] == "docker"
        assert "alpine" in args_falkor
        assert "tar" in args_falkor

        args_qdrant = mock_run.call_args_list[1][0][0]
        assert args_qdrant[0] == "docker"

    @patch("backup_restore.subprocess.run")
    @patch("backup_restore.os.path.exists")
    @patch("backup_restore.os.makedirs")
    def test_backup_container_mode(self, mock_makedirs, mock_exists, mock_run):
        # Setup: Container mode (/mnt paths exist)
        # We need to simulate exists returning True for the specific mount paths
        def side_effect(path):
            if path in ["/mnt/falkor_data", "/mnt/qdrant_data"]:
                return True
            return False

        mock_exists.side_effect = side_effect
        mock_run.return_value = MagicMock(returncode=0)

        # Execute
        backup_restore.backup(tag="test_container")

        # Verify: Should use direct tar calls
        assert mock_run.call_count == 2

        args_falkor = mock_run.call_args_list[0][0][0]
        assert args_falkor[0] == "tar"
        assert args_falkor[2].endswith("falkor_data.tar.gz")

        args_qdrant = mock_run.call_args_list[1][0][0]
        assert args_qdrant[0] == "tar"
        assert args_qdrant[2].endswith("qdrant_data.tar.gz")
