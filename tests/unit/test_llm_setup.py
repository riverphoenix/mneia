from __future__ import annotations

from unittest.mock import MagicMock, patch

from mneia.core.llm_setup import (
    CONNECTOR_HELP,
    PROVIDER_DISPLAY,
    PROVIDER_MODELS,
    get_connector_help,
    get_models_for_provider,
    list_ollama_models,
)


def test_provider_models_has_all_api_providers() -> None:
    assert "anthropic" in PROVIDER_MODELS
    assert "openai" in PROVIDER_MODELS
    assert "google" in PROVIDER_MODELS


def test_provider_display_has_all_providers() -> None:
    assert "ollama" in PROVIDER_DISPLAY
    assert "anthropic" in PROVIDER_DISPLAY
    assert "openai" in PROVIDER_DISPLAY
    assert "google" in PROVIDER_DISPLAY


def test_get_connector_help_known() -> None:
    help_info = get_connector_help("obsidian")
    assert help_info is not None
    assert "description" in help_info
    assert "prerequisites" in help_info
    assert "setup_help" in help_info
    assert "next_steps" in help_info


def test_get_connector_help_unknown() -> None:
    assert get_connector_help("nonexistent") is None


def test_get_models_for_api_provider() -> None:
    models = get_models_for_provider("anthropic")
    assert len(models) > 0
    assert any("claude" in m for m in models)


def test_get_models_for_ollama_unreachable() -> None:
    models = list_ollama_models("http://localhost:99999")
    assert models == []


def test_get_models_for_unknown_provider() -> None:
    models = get_models_for_provider("unknown_provider")
    assert models == []


@patch("mneia.core.llm_setup.httpx.get")
def test_list_ollama_models_success(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "phi3:mini"},
            {"name": "llama3.2:latest"},
            {"name": "nomic-embed-text"},
        ]
    }
    mock_get.return_value = mock_resp

    models = list_ollama_models()
    assert "phi3:mini" in models
    assert "llama3.2:latest" in models
    assert len(models) == 3


def test_connector_help_covers_common_connectors() -> None:
    expected = ["obsidian", "slack", "github", "gmail", "notion", "linear"]
    for name in expected:
        assert name in CONNECTOR_HELP, f"Missing help for {name}"
