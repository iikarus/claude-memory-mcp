import os
import shutil
import time
import unittest
from unittest.mock import patch

from claude_memory.lock_manager import LockManager


class TestLockFallback(unittest.TestCase):
    def setUp(self):
        # Ensure clean state
        self.lock_dir = os.path.join(os.getcwd(), ".locks")
        if os.path.exists(self.lock_dir):
            shutil.rmtree(self.lock_dir)

    def tearDown(self):
        if os.path.exists(self.lock_dir):
            shutil.rmtree(self.lock_dir)

    @patch("redis.Redis")
    def test_fallback_initialization(self, mock_redis):
        # Simulate Redis failure
        mock_redis.side_effect = Exception("Connection refused")

        manager = LockManager()

        self.assertIsNone(manager.client)
        self.assertTrue(os.path.exists(self.lock_dir))

    @patch("redis.Redis")
    def test_file_acquire_release(self, mock_redis):
        mock_redis.side_effect = Exception("Connection refused")
        manager = LockManager()
        project_id = "test_project"

        # 1. Acquire
        result = manager.acquire(project_id)
        self.assertTrue(result)

        lock_path = os.path.join(self.lock_dir, f"{project_id}.lock")
        self.assertTrue(os.path.exists(lock_path))

        # 2. Re-acquire (should fail/wait)
        # We set a short timeout to not block test
        start = time.time()
        result_2 = manager.acquire(project_id, timeout=1)
        duration = time.time() - start

        self.assertFalse(result_2)
        self.assertGreaterEqual(duration, 1.0)

        # 3. Release
        manager.release(project_id)
        self.assertFalse(os.path.exists(lock_path))

    @patch("redis.Redis")
    def test_context_manager(self, mock_redis):
        mock_redis.side_effect = Exception("Connection refused")
        manager = LockManager()
        project_id = "ctx_project"

        lock_path = os.path.join(self.lock_dir, f"{project_id}.lock")

        with manager.lock(project_id):
            self.assertTrue(os.path.exists(lock_path))

        self.assertFalse(os.path.exists(lock_path))


if __name__ == "__main__":
    unittest.main()
