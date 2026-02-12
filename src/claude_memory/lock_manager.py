"""Project-scoped distributed locking via Redis with file-system fallback."""

import asyncio
import logging
import os
import time
from typing import Any

import redis

logger = logging.getLogger(__name__)


class ProjectLock:
    """
    Simulates a lock object behavior similar to threading.Lock but distributed via Redis.
    Supports both sync (with) and async (async with) context managers.
    """

    def __init__(self, manager: "LockManager", project_id: str):
        """Bind this lock to a specific manager and project."""
        self.manager = manager
        self.project_id = project_id

    def acquire(self, timeout: int = 5) -> bool:
        """Synchronously acquire the project lock."""
        return self.manager.acquire(self.project_id, timeout)

    async def async_acquire(self, timeout: int = 5) -> bool:
        """Non-blocking acquire using asyncio.sleep."""
        return await self.manager.async_acquire(self.project_id, timeout)

    def release(self) -> None:
        """Release the project lock."""
        self.manager.release(self.project_id)

    def __enter__(self) -> "ProjectLock":
        """Enter sync context manager — acquire lock or raise TimeoutError."""
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock for project {self.project_id}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit sync context manager — release the lock."""
        self.release()

    async def __aenter__(self) -> "ProjectLock":
        """Enter async context manager — acquire lock or raise TimeoutError."""
        if not await self.async_acquire():
            raise TimeoutError(f"Could not acquire lock for project {self.project_id}")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager — release the lock."""
        self.release()


class LockManager:
    """
    Manages Project-Based Locking using Redis.
    """

    def __init__(self, host: str | None = None, port: int | None = None):
        """Connect to Redis for locking, falling back to file locks if unavailable."""
        h = host or (os.getenv("REDIS_HOST") or os.getenv("FALKORDB_HOST", "localhost"))
        self.host: str = str(h) if h else "localhost"

        if port is not None:
            self.port = port
        else:
            raw_port = os.getenv("REDIS_PORT") or os.getenv("FALKORDB_PORT") or "6379"
            self.port = int(raw_port)

        self.password: str | None = os.getenv("REDIS_PASSWORD") or os.getenv("FALKORDB_PASSWORD")

        # Reuse the same Redis instance as FalkorDB (port 6379 usually)
        # FalkorDB is a Redis module, so standard Redis commands work alongside GRAPH commands.
        self.client: redis.Redis | None = None
        try:
            self.client = redis.Redis(
                host=self.host, port=self.port, password=self.password, decode_responses=True
            )
            # Test connection
            self.client.ping()
        except Exception as e:
            logger.warning("Redis unavailable (%s). Swapping to FileLock fallback strategy.", e)
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
        """Release a lock via Redis or file."""
        if self.client:
            self._release_redis(project_id)
        else:
            self._release_file(project_id)

    # Redis Impl
    def _acquire_redis(self, project_id: str, timeout: int) -> bool:
        """Spin-acquire a Redis-based lock with timeout."""
        lock_key = f"lock:project:{project_id}"
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.client and self.client.set(lock_key, "locked", nx=True, ex=timeout + 5):
                return True
            time.sleep(0.1)
        logger.warning("Failed to acquire Redis lock for project %s", project_id)
        return False

    def _release_redis(self, project_id: str) -> None:
        """Delete the Redis lock key."""
        if self.client:
            self.client.delete(f"lock:project:{project_id}")

    # File Impl
    def _acquire_file(self, project_id: str, timeout: int) -> bool:
        """Spin-acquire a file-based lock with stale detection."""
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
                    with open(lock_path) as f:
                        content = f.read()
                    if content and (time.time() - float(content)) > (timeout + 5):
                        # Stale, remove and retry
                        os.remove(lock_path)
                        continue
                except (FileNotFoundError, ValueError):
                    pass
                time.sleep(0.1)
        logger.warning("Failed to acquire File lock for project %s", project_id)
        return False

    def _release_file(self, project_id: str) -> None:
        """Remove the lock file."""
        lock_path = os.path.join(self.lock_dir, f"{project_id}.lock")
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass

    def lock(self, project_id: str) -> ProjectLock:
        """Return a ProjectLock context manager for the given project."""
        return ProjectLock(self, project_id)

    async def async_acquire(self, project_id: str, timeout: int = 5) -> bool:
        """Non-blocking acquire using asyncio.sleep instead of time.sleep."""
        if self.client:
            return await self._async_acquire_redis(project_id, timeout)
        else:
            return await self._async_acquire_file(project_id, timeout)

    async def _async_acquire_redis(self, project_id: str, timeout: int) -> bool:
        """Async spin-acquire a Redis-based lock with timeout."""
        lock_key = f"lock:project:{project_id}"
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.client and self.client.set(lock_key, "locked", nx=True, ex=timeout + 5):
                return True
            await asyncio.sleep(0.1)
        logger.warning("Failed to acquire Redis lock for project %s", project_id)
        return False

    async def _async_acquire_file(self, project_id: str, timeout: int) -> bool:
        """Async spin-acquire a file-based lock with stale detection."""
        lock_path = os.path.join(self.lock_dir, f"{project_id}.lock")
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                with open(lock_path, "x") as f:
                    f.write(str(time.time()))
                return True
            except FileExistsError:
                try:
                    with open(lock_path) as f:
                        content = f.read()
                    if content and (time.time() - float(content)) > (timeout + 5):
                        os.remove(lock_path)
                        continue
                except (FileNotFoundError, ValueError):
                    pass
                await asyncio.sleep(0.1)
        logger.warning("Failed to acquire File lock for project %s", project_id)
        return False
