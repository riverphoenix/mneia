from __future__ import annotations

import time

from mneia.core.metrics import MetricsCollector


def test_counter():
    MetricsCollector.reset()
    m = MetricsCollector.get()
    c = m.counter("docs_processed")
    assert c.value == 0
    c.increment()
    c.increment(5)
    assert c.value == 6


def test_gauge():
    MetricsCollector.reset()
    m = MetricsCollector.get()
    g = m.gauge("memory_mb")
    g.set(512.5)
    assert g.value == 512.5


def test_timer():
    MetricsCollector.reset()
    m = MetricsCollector.get()
    t = m.timer("llm_latency")
    t.record(0.5)
    t.record(1.5)
    assert t.count == 2
    assert t.total_seconds == 2.0
    assert t.average == 1.0


def test_timer_context():
    MetricsCollector.reset()
    m = MetricsCollector.get()
    with m.time("operation"):
        time.sleep(0.01)
    t = m.timer("operation")
    assert t.count == 1
    assert t.total_seconds >= 0.01


def test_singleton():
    MetricsCollector.reset()
    m1 = MetricsCollector.get()
    m2 = MetricsCollector.get()
    assert m1 is m2


def test_snapshot():
    MetricsCollector.reset()
    m = MetricsCollector.get()
    m.counter("a").increment(3)
    m.gauge("b").set(42.0)
    m.timer("c").record(1.0)

    snap = m.snapshot()
    assert snap["counter.a"]["value"] == 3
    assert snap["gauge.b"]["value"] == 42.0
    assert snap["timer.c"]["count"] == 1


def test_timer_average_empty():
    MetricsCollector.reset()
    m = MetricsCollector.get()
    t = m.timer("empty")
    assert t.average == 0.0
