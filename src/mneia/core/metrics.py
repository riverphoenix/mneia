from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class MetricCounter:
    value: int = 0

    def increment(self, amount: int = 1) -> None:
        self.value += amount


@dataclass
class MetricGauge:
    value: float = 0.0

    def set(self, value: float) -> None:
        self.value = value


@dataclass
class MetricTimer:
    total_seconds: float = 0.0
    count: int = 0

    def record(self, duration: float) -> None:
        self.total_seconds += duration
        self.count += 1

    @property
    def average(self) -> float:
        return self.total_seconds / self.count if self.count > 0 else 0.0


class MetricsCollector:
    _instance: MetricsCollector | None = None

    def __init__(self) -> None:
        self._counters: dict[str, MetricCounter] = {}
        self._gauges: dict[str, MetricGauge] = {}
        self._timers: dict[str, MetricTimer] = {}

    @classmethod
    def get(cls) -> MetricsCollector:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def counter(self, name: str) -> MetricCounter:
        if name not in self._counters:
            self._counters[name] = MetricCounter()
        return self._counters[name]

    def gauge(self, name: str) -> MetricGauge:
        if name not in self._gauges:
            self._gauges[name] = MetricGauge()
        return self._gauges[name]

    def timer(self, name: str) -> MetricTimer:
        if name not in self._timers:
            self._timers[name] = MetricTimer()
        return self._timers[name]

    def time(self, name: str) -> _TimerContext:
        return _TimerContext(self.timer(name))

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        result: dict[str, dict[str, float | int]] = {}
        for name, c in self._counters.items():
            result[f"counter.{name}"] = {"value": c.value}
        for name, g in self._gauges.items():
            result[f"gauge.{name}"] = {"value": g.value}
        for name, t in self._timers.items():
            result[f"timer.{name}"] = {
                "total_seconds": round(t.total_seconds, 4),
                "count": t.count,
                "avg_seconds": round(t.average, 4),
            }
        return result


class _TimerContext:
    def __init__(self, timer: MetricTimer) -> None:
        self._timer = timer
        self._start = 0.0

    def __enter__(self) -> _TimerContext:
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: object) -> None:
        self._timer.record(time.monotonic() - self._start)
