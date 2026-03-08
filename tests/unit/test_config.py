from __future__ import annotations

from pathlib import Path

from mneia.config import ConnectorConfig, LLMConfig, MneiaConfig


def test_default_config():
    config = MneiaConfig()
    assert config.llm.provider == "ollama"
    assert config.llm.model == "phi3:mini"
    assert config.auto_generate_context is True
    assert config.log_level == "info"


def test_config_save_load(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config = MneiaConfig()
    config.llm.model = "mistral:7b"
    config.connectors["obsidian"] = ConnectorConfig(enabled=True, settings={"vault_path": "/test"})

    import mneia.config as cfg

    original_path = cfg.CONFIG_PATH
    original_dir = cfg.MNEIA_DIR
    try:
        cfg.CONFIG_PATH = config_path
        cfg.MNEIA_DIR = tmp_path
        config.save()

        loaded = MneiaConfig.load()
        assert loaded.llm.model == "mistral:7b"
        assert loaded.connectors["obsidian"].enabled is True
        assert loaded.connectors["obsidian"].settings["vault_path"] == "/test"
    finally:
        cfg.CONFIG_PATH = original_path
        cfg.MNEIA_DIR = original_dir


def test_config_set_value():
    config = MneiaConfig()
    config.llm.model = "phi3:mini"
    assert config.llm.model == "phi3:mini"

    config.llm.temperature = 0.5
    assert config.llm.temperature == 0.5


def test_llm_config_defaults():
    llm = LLMConfig()
    assert llm.provider == "ollama"
    assert llm.ollama_base_url == "http://localhost:11434"
    assert llm.temperature == 0.1
    assert llm.max_tokens == 2048
