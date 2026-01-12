import logging
import os
import time
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)


class ProjectLock:
    """
    Simulates a lock object behavior similar to threading.Lock but distributed via Redis.
    """

    def __init__(self, manager: "LockManager", project_id: str):
        self.manager = manager
        self.project_id = project_id

    def acquire(self, timeout: int = 5) -> bool:
        return self.manager.acquire(self.project_id, timeout)

    def release(self) -> None:
        self.manager.release(self.project_id)

    def __enter__(self) -> "ProjectLock":
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock for project {self.project_id}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


class LockManager:
    """
    Manages Project-Based Locking using Redis.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        h = host or os.getenv("FALKORDB_HOST", "localhost")
        self.host: str = str(h) if h else "localhost"

        p = port or os.getenv("FALKORDB_PORT", 6379)
        self.port: int = int(p) if p else 6379

        self.password: Optional[str] = os.getenv("FALKORDB_PASSWORD")

        # Reuse the same Redis instance as FalkorDB (port 6379 usually)
        # FalkorDB is a Redis module, so standard Redis commands work alongside GRAPH commands.
        self.client = redis.Redis(
            host=self.host, port=self.port, password=self.password, decode_responses=True
        )

    def acquire(self, project_id: str, timeout: int = 5) -> bool:
        """
        Acquire a lock for the given project_id.
        Waits up to 'timeout' seconds.
        """
        lock_key = f"lock:project:{project_id}"
        end_time = time.time() + timeout

        while time.time() < end_time:
            # simple SETNX with expiry
            if self.client.set(lock_key, "locked", nx=True, ex=timeout + 5):
                return True
            time.sleep(0.1)

        logger.warning(f"Failed to acquire lock for project {project_id} after {timeout}s")
        return False

    def release(self, project_id: str) -> None:
        """Release the lock."""
        lock_key = f"lock:project:{project_id}"
        self.client.delete(lock_key)

    def lock(self, project_id: str) -> ProjectLock:
        """Returns a context manager for locking."""
        return ProjectLock(self, project_id)
