from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

MNEIA_DIR = Path.home() / ".mneia"
CONFIG_PATH = MNEIA_DIR / "config.json"
DATA_DIR = MNEIA_DIR / "data"
CONTEXT_DIR = MNEIA_DIR / "context"
TEMPLATES_DIR = MNEIA_DIR / "templates"
LOGS_DIR = MNEIA_DIR / "logs"
SOCKET_PATH = MNEIA_DIR / "mneia.sock"


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "phi3:mini"
    embedding_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    temperature: float = 0.1
    max_tokens: int = 2048


class ConnectorConfig(BaseModel):
    enabled: bool = False
    poll_interval_seconds: int = 300
    settings: dict[str, Any] = Field(default_factory=dict)
    last_checkpoint: str | None = None


class SafetyConfig(BaseModel):
    auto_approve_low_risk: bool = True
    approval_ttl_hours: int = 24
    blocked_operations: list[str] = Field(default_factory=list)


class MneiaConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    connectors: dict[str, ConnectorConfig] = Field(default_factory=dict)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    context_output_dir: str = str(CONTEXT_DIR)
    auto_generate_context: bool = True
    context_regenerate_interval_minutes: int = 30
    context_min_changes_for_regen: int = 5
    enrichment_scrape_enabled: bool = False
    enrichment_max_scrape_pages: int = 5
    enrichment_scrape_delay_seconds: float = 2.0
    autonomous_enabled: bool = True
    autonomous_interval_minutes: int = 30
    autonomous_max_actions: int = 5
    autonomous_creativity_temperature: float = 0.7
    max_memory_mb: int = 2048
    log_level: str = "info"

    @classmethod
    def load(cls) -> MneiaConfig:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cls.model_validate(data)
        return cls()

    def save(self) -> None:
        MNEIA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            self.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def set_value(self, key: str, value: str) -> None:
        parts = key.split(".")
        obj: Any = self
        for part in parts[:-1]:
            if isinstance(obj, dict):
                obj = obj[part]
            else:
                obj = getattr(obj, part)
        final_key = parts[-1]
        if isinstance(obj, dict):
            obj[final_key] = value
        else:
            current = getattr(obj, final_key)
            if isinstance(current, bool):
                obj.__dict__[final_key] = value.lower() in ("true", "1", "yes")
            elif isinstance(current, int):
                obj.__dict__[final_key] = int(value)
            elif isinstance(current, float):
                obj.__dict__[final_key] = float(value)
            else:
                obj.__dict__[final_key] = value
        self.save()

    def get_value(self, key: str) -> Any:
        parts = key.split(".")
        obj: Any = self
        for part in parts:
            if isinstance(obj, dict):
                obj = obj[part]
            else:
                obj = getattr(obj, part)
        return obj


def ensure_dirs() -> None:
    for d in [MNEIA_DIR, DATA_DIR, CONTEXT_DIR, TEMPLATES_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
