from __future__ import annotations

import time

from mneia.core.llm import CircuitBreaker


def test_starts_closed():
    cb = CircuitBreaker(failure_threshold=3)
    assert cb.is_open is False


def test_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is False
    cb.record_failure()
    assert cb.is_open is True


def test_success_resets():
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert cb.is_open is False


def test_resets_after_timeout():
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)
    cb.record_failure()
    assert cb.is_open is True
    time.sleep(0.06)
    assert cb.is_open is False


def test_stays_open_before_timeout():
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10)
    cb.record_failure()
    assert cb.is_open is True
