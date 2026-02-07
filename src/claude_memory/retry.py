"""Retry utility with exponential backoff for transient connection failures."""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default transient exceptions to retry on
_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Try to add Redis-specific exceptions if available
try:
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    _TRANSIENT_EXCEPTIONS = (*_TRANSIENT_EXCEPTIONS, RedisConnectionError, RedisTimeoutError)
except ImportError:  # pragma: no cover
    pass


def retry_on_transient(  # noqa: C901
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    exceptions: tuple[type[BaseException], ...] | None = None,
) -> Callable[..., Any]:
    """Decorator: retry a function on transient connection errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds (doubles each retry).
        max_delay: Maximum delay cap in seconds.
        exceptions: Tuple of exception types to catch. Defaults to common transient errors.
    """
    retryable = exceptions or _TRANSIENT_EXCEPTIONS

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a sync or async function with retry logic."""

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Async retry wrapper with exponential backoff."""
            for attempt in range(max_retries + 1):  # pragma: no branch
                try:
                    return await func(*args, **kwargs)
                except retryable as exc:
                    if attempt == max_retries:
                        logger.error(
                            "Failed after %d retries: %s — %s",
                            max_retries,
                            func.__name__,
                            exc,
                        )
                        raise
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "Retry %d/%d for %s in %.1fs — %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Sync retry wrapper with exponential backoff."""
            for attempt in range(max_retries + 1):  # pragma: no branch
                try:
                    return func(*args, **kwargs)
                except retryable as exc:
                    if attempt == max_retries:
                        logger.error(
                            "Failed after %d retries: %s — %s",
                            max_retries,
                            func.__name__,
                            exc,
                        )
                        raise
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "Retry %d/%d for %s in %.1fs — %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        delay,
                        exc,
                    )
                    time.sleep(delay)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
