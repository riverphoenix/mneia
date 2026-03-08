from __future__ import annotations

import pytest

from mneia.core.retry import retry


async def test_retry_success_first_attempt():
    call_count = 0

    @retry(max_attempts=3, backoff=0.01)
    async def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await succeed()
    assert result == "ok"
    assert call_count == 1


async def test_retry_success_after_failures():
    call_count = 0

    @retry(max_attempts=3, backoff=0.01)
    async def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("not yet")
        return "ok"

    result = await fail_then_succeed()
    assert result == "ok"
    assert call_count == 3


async def test_retry_all_attempts_fail():
    call_count = 0

    @retry(max_attempts=3, backoff=0.01)
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("always fails")

    with pytest.raises(ValueError, match="always fails"):
        await always_fail()
    assert call_count == 3


async def test_retry_specific_exceptions():
    call_count = 0

    @retry(max_attempts=3, backoff=0.01, exceptions=(ValueError,))
    async def raise_type_error():
        nonlocal call_count
        call_count += 1
        raise TypeError("wrong type")

    with pytest.raises(TypeError):
        await raise_type_error()
    assert call_count == 1


async def test_retry_backoff_multiplier():
    call_count = 0

    @retry(max_attempts=2, backoff=0.01, backoff_multiplier=2.0)
    async def fail_once():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("fail")
        return "ok"

    result = await fail_once()
    assert result == "ok"
    assert call_count == 2
