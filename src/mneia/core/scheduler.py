from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class AsyncScheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._running = True

    async def schedule_recurring(
        self,
        name: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        interval_seconds: int,
        initial_delay: int = 0,
    ) -> None:
        async def _loop() -> None:
            if initial_delay > 0:
                await asyncio.sleep(initial_delay)
            while self._running:
                try:
                    await coro_fn()
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception(f"Scheduled task {name} failed")
                await asyncio.sleep(interval_seconds)

        self._tasks[name] = asyncio.create_task(_loop(), name=name)

    def cancel(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()

    async def stop_all(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
