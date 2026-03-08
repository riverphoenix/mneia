from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class AgentResult:
    agent_name: str
    documents_processed: int = 0
    entities_extracted: int = 0
    associations_created: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self._state = AgentState.IDLE

    @property
    def state(self) -> AgentState:
        return self._state

    @abstractmethod
    async def run(self, **kwargs: Any) -> AgentResult:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...
