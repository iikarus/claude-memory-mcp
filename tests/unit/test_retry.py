"""Tests for the retry utility with exponential backoff."""

from unittest.mock import patch

import pytest

from claude_memory.retry import retry_on_transient


class TestRetryOnTransientSync:
    """Test sync retry behavior."""

    def test_succeeds_first_try(self) -> None:
        """Function succeeds on first call — no retries needed."""

        @retry_on_transient(max_retries=3)
        def fn() -> str:
            """Return ok."""
            return "ok"

        assert fn() == "ok"

    def test_retries_on_connection_error(self) -> None:
        """Retries on ConnectionError and eventually succeeds."""
        call_count = 0

        @retry_on_transient(max_retries=3, base_delay=0.01)
        def fn() -> str:
            """Fail twice then succeed."""
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("refused")
            return "recovered"

        assert fn() == "recovered"
        assert call_count == 3

    def test_retries_on_timeout_error(self) -> None:
        """Retries on TimeoutError."""
        call_count = 0

        @retry_on_transient(max_retries=3, base_delay=0.01)
        def fn() -> str:
            """Fail once then succeed."""
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timed out")
            return "ok"

        assert fn() == "ok"
        assert call_count == 2

    def test_raises_after_max_retries(self) -> None:
        """Raises the original exception after exhausting retries."""

        @retry_on_transient(max_retries=2, base_delay=0.01)
        def fn() -> str:
            """Always fail."""
            raise ConnectionError("permanent failure")

        with pytest.raises(ConnectionError, match="permanent failure"):
            fn()

    def test_non_retryable_error_not_caught(self) -> None:
        """Non-transient exceptions are raised immediately."""

        @retry_on_transient(max_retries=3, base_delay=0.01)
        def fn() -> str:
            """Raise ValueError."""
            raise ValueError("not transient")

        with pytest.raises(ValueError, match="not transient"):
            fn()

    def test_custom_exceptions(self) -> None:
        """Custom exception types can be specified."""
        call_count = 0

        @retry_on_transient(max_retries=2, base_delay=0.01, exceptions=(ValueError,))
        def fn() -> str:
            """Fail once with ValueError."""
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("custom")
            return "ok"

        assert fn() == "ok"

    def test_max_delay_cap(self) -> None:
        """Delay is capped at max_delay."""
        call_count = 0

        @retry_on_transient(max_retries=5, base_delay=1.0, max_delay=2.0)
        def fn() -> str:
            """Fail 4 times then succeed."""
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise ConnectionError("fail")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            result = fn()
            assert result == "ok"
            # Verify delays are capped at 2.0
            for call in mock_sleep.call_args_list:
                assert call[0][0] <= 2.0


class TestRetryOnTransientAsync:
    """Test async retry behavior."""

    @pytest.mark.asyncio
    async def test_async_succeeds_first_try(self) -> None:
        """Async function succeeds on first call."""

        @retry_on_transient(max_retries=3)
        async def fn() -> str:
            """Return ok."""
            return "ok"

        assert await fn() == "ok"

    @pytest.mark.asyncio
    async def test_async_retries_on_connection_error(self) -> None:
        """Async retries on ConnectionError."""
        call_count = 0

        @retry_on_transient(max_retries=3, base_delay=0.01)
        async def fn() -> str:
            """Fail twice then succeed."""
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("refused")
            return "recovered"

        assert await fn() == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_raises_after_max_retries(self) -> None:
        """Async raises after exhausting retries."""

        @retry_on_transient(max_retries=2, base_delay=0.01)
        async def fn() -> str:
            """Always fail."""
            raise TimeoutError("permanent")

        with pytest.raises(TimeoutError, match="permanent"):
            await fn()

    @pytest.mark.asyncio
    async def test_async_non_retryable_not_caught(self) -> None:
        """Async non-transient exceptions are raised immediately."""

        @retry_on_transient(max_retries=3, base_delay=0.01)
        async def fn() -> str:
            """Raise KeyError."""
            raise KeyError("not transient")

        with pytest.raises(KeyError, match="not transient"):
            await fn()

    @pytest.mark.asyncio
    async def test_async_os_error_retried(self) -> None:
        """OSError is retried (it's in the default exception list)."""
        call_count = 0

        @retry_on_transient(max_retries=2, base_delay=0.01)
        async def fn() -> str:
            """Fail once with OSError."""
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("network unreachable")
            return "ok"

        assert await fn() == "ok"
        assert call_count == 2
