from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mneia.config import MneiaConfig


@pytest.fixture()
def tmp_config(monkeypatch, tmp_path):
    config_dir = tmp_path / ".mneia"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    monkeypatch.setattr("mneia.config.MNEIA_DIR", config_dir)
    monkeypatch.setattr("mneia.config.CONFIG_PATH", config_path)
    return config_path


def test_env_override_provider(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_LLM_PROVIDER", "anthropic")
    config = MneiaConfig.load()
    assert config.llm.provider == "anthropic"


def test_env_override_model(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_LLM_MODEL", "claude-3-opus")
    config = MneiaConfig.load()
    assert config.llm.model == "claude-3-opus"


def test_env_override_api_key(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_ANTHROPIC_API_KEY", "sk-ant-test123")
    config = MneiaConfig.load()
    assert config.llm.anthropic_api_key == "sk-ant-test123"


def test_env_override_openai_key(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_OPENAI_API_KEY", "sk-openai-test")
    config = MneiaConfig.load()
    assert config.llm.openai_api_key == "sk-openai-test"


def test_env_override_google_key(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_GOOGLE_API_KEY", "google-test-key")
    config = MneiaConfig.load()
    assert config.llm.google_api_key == "google-test-key"


def test_env_override_log_level(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_LOG_LEVEL", "debug")
    config = MneiaConfig.load()
    assert config.log_level == "debug"


def test_env_override_bool(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_AUTONOMOUS_ENABLED", "false")
    config = MneiaConfig.load()
    assert config.autonomous_enabled is False


def test_env_override_bool_true(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_AUTONOMOUS_ENABLED", "true")
    config = MneiaConfig.load()
    assert config.autonomous_enabled is True


def test_env_overrides_config_file(monkeypatch, tmp_config):
    config_data = {"llm": {"provider": "ollama", "model": "phi3:mini"}}
    tmp_config.write_text(json.dumps(config_data))
    monkeypatch.setenv("MNEIA_LLM_PROVIDER", "openai")
    config = MneiaConfig.load()
    assert config.llm.provider == "openai"
    assert config.llm.model == "phi3:mini"


def test_no_env_uses_defaults(monkeypatch, tmp_config):
    for key in [
        "MNEIA_LLM_PROVIDER", "MNEIA_LLM_MODEL",
        "MNEIA_ANTHROPIC_API_KEY", "MNEIA_OPENAI_API_KEY",
        "MNEIA_GOOGLE_API_KEY", "MNEIA_LOG_LEVEL",
        "MNEIA_AUTONOMOUS_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)
    config = MneiaConfig.load()
    assert config.llm.provider == "ollama"
    assert config.log_level == "info"


def test_env_override_embedding_model(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_LLM_EMBEDDING_MODEL", "text-embedding-3-small")
    config = MneiaConfig.load()
    assert config.llm.embedding_model == "text-embedding-3-small"


def test_env_override_ollama_url(monkeypatch, tmp_config):
    monkeypatch.setenv("MNEIA_OLLAMA_BASE_URL", "http://myserver:11434")
    config = MneiaConfig.load()
    assert config.llm.ollama_base_url == "http://myserver:11434"
