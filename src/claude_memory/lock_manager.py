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
        self.client: Optional["redis.Redis[str]"] = None
        try:
            self.client = redis.Redis(
                host=self.host, port=self.port, password=self.password, decode_responses=True
            )
            # Test connection
            self.client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}). Swapping to FileLock fallback strategy.")
            self.client = None
            # Ensure lock directory exists
            self.lock_dir = os.path.join(os.getcwd(), ".locks")
            os.makedirs(self.lock_dir, exist_ok=True)

    def acquire(self, project_id: str, timeout: int = 5) -> bool:
        """
        Acquire a lock via Redis or File.
        """
        if self.client:
            return self._acquire_redis(project_id, timeout)
        else:
            return self._acquire_file(project_id, timeout)

    def release(self, project_id: str) -> None:
        if self.client:
            self._release_redis(project_id)
        else:
            self._release_file(project_id)

    # Redis Impl
    def _acquire_redis(self, project_id: str, timeout: int) -> bool:
        lock_key = f"lock:project:{project_id}"
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.client and self.client.set(lock_key, "locked", nx=True, ex=timeout + 5):
                return True
            time.sleep(0.1)
        logger.warning(f"Failed to acquire Redis lock for project {project_id}")
        return False

    def _release_redis(self, project_id: str) -> None:
        if self.client:
            self.client.delete(f"lock:project:{project_id}")

    # File Impl
    def _acquire_file(self, project_id: str, timeout: int) -> bool:
        lock_path = os.path.join(self.lock_dir, f"{project_id}.lock")
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # Exclusive creation
                with open(lock_path, "x") as f:
                    f.write(str(time.time()))
                return True
            except FileExistsError:
                # Check for stale lock (timeout + buffer)
                try:
                    with open(lock_path, "r") as f:
                        content = f.read()
                    if content and (time.time() - float(content)) > (timeout + 5):
                        # Stale, remove and retry
                        os.remove(lock_path)
                        continue
                except (FileNotFoundError, ValueError):
                    pass
                time.sleep(0.1)
        logger.warning(f"Failed to acquire File lock for project {project_id}")
        return False

    def _release_file(self, project_id: str) -> None:
        lock_path = os.path.join(self.lock_dir, f"{project_id}.lock")
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass

    def lock(self, project_id: str) -> ProjectLock:
        return ProjectLock(self, project_id)
