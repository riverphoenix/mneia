from __future__ import annotations

import json
import os
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
PID_PATH = MNEIA_DIR / "daemon.pid"
STATS_DB_PATH = DATA_DIR / "agent_stats.db"


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "phi3:mini"
    embedding_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
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
    hermes_enabled: bool = True
    hermes_model: str = ""
    hermes_max_iterations: int = 10
    max_memory_mb: int = 2048
    log_level: str = "info"

    @classmethod
    def load(cls) -> MneiaConfig:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config = cls.model_validate(data)
        else:
            config = cls()
        config._apply_env_overrides()
        return config

    def _apply_env_overrides(self) -> None:
        env_mappings: dict[str, str] = {
            "MNEIA_LLM_PROVIDER": "llm.provider",
            "MNEIA_LLM_MODEL": "llm.model",
            "MNEIA_LLM_EMBEDDING_MODEL": "llm.embedding_model",
            "MNEIA_OLLAMA_BASE_URL": "llm.ollama_base_url",
            "MNEIA_ANTHROPIC_API_KEY": "llm.anthropic_api_key",
            "MNEIA_OPENAI_API_KEY": "llm.openai_api_key",
            "MNEIA_GOOGLE_API_KEY": "llm.google_api_key",
            "MNEIA_LOG_LEVEL": "log_level",
            "MNEIA_AUTONOMOUS_ENABLED": "autonomous_enabled",
        }
        for env_key, config_path in env_mappings.items():
            val = os.environ.get(env_key)
            if val is not None:
                self._set_value_no_save(config_path, val)

    def _set_value_no_save(self, key: str, value: str) -> None:
        parts = key.split(".")
        obj: Any = self
        for part in parts[:-1]:
            obj = getattr(obj, part)
        final_key = parts[-1]
        current = getattr(obj, final_key)
        if isinstance(current, bool):
            obj.__dict__[final_key] = value.lower() in ("true", "1", "yes")
        elif isinstance(current, int):
            obj.__dict__[final_key] = int(value)
        elif isinstance(current, float):
            obj.__dict__[final_key] = float(value)
        else:
            obj.__dict__[final_key] = value

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
