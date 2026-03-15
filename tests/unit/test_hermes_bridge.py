from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.config import LLMConfig, MneiaConfig


def test_is_hermes_available_when_installed():
    mock_run_agent = MagicMock()
    mock_run_agent.AIAgent = MagicMock()
    with patch.dict("sys.modules", {"run_agent": mock_run_agent}):
        from mneia.agents import hermes_bridge
        import importlib

        importlib.reload(hermes_bridge)
        assert hermes_bridge.is_hermes_available() is True


def test_is_hermes_available_when_not_installed():
    with patch.dict("sys.modules", {"run_agent": None}):
        from mneia.agents.hermes_bridge import is_hermes_available

        assert is_hermes_available() is False


def test_translate_llm_config_ollama():
    from mneia.agents.hermes_bridge import _translate_llm_config

    config = LLMConfig(provider="ollama", model="phi3:mini", ollama_base_url="http://localhost:11434")
    result = _translate_llm_config(config)
    assert result["model"] == "ollama/phi3:mini"
    assert result["api_base"] == "http://localhost:11434"


def test_translate_llm_config_anthropic():
    from mneia.agents.hermes_bridge import _translate_llm_config

    config = LLMConfig(provider="anthropic", model="claude-3-haiku", anthropic_api_key="sk-test")
    result = _translate_llm_config(config)
    assert result["model"] == "anthropic/claude-3-haiku"
    assert result["api_key"] == "sk-test"


def test_translate_llm_config_openai():
    from mneia.agents.hermes_bridge import _translate_llm_config

    config = LLMConfig(provider="openai", model="gpt-4o", openai_api_key="sk-test")
    result = _translate_llm_config(config)
    assert result["model"] == "gpt-4o"
    assert result["api_key"] == "sk-test"


def test_translate_llm_config_google():
    from mneia.agents.hermes_bridge import _translate_llm_config

    config = LLMConfig(provider="google", model="gemini-pro", google_api_key="key-test")
    result = _translate_llm_config(config)
    assert result["model"] == "gemini/gemini-pro"
    assert result["api_key"] == "key-test"


def test_translate_llm_config_unknown():
    from mneia.agents.hermes_bridge import _translate_llm_config

    config = LLMConfig(provider="custom", model="my-model")
    result = _translate_llm_config(config)
    assert result["model"] == "my-model"


def test_hermes_home_path():
    from mneia.agents.hermes_bridge import HERMES_HOME
    from mneia.config import MNEIA_DIR

    assert HERMES_HOME == MNEIA_DIR / "hermes"


def test_run_hermes_cycle_empty_docs():
    from mneia.agents.hermes_bridge import run_hermes_cycle

    agent = MagicMock()
    result = run_hermes_cycle(agent, [])
    assert result is None
    agent.run_conversation.assert_not_called()


def test_run_hermes_cycle_with_docs():
    from mneia.agents.hermes_bridge import run_hermes_cycle

    agent = MagicMock()
    agent.run_conversation.return_value = "Found 3 connections between documents."

    summaries = [
        "[gmail] Budget email: Discussion about Q1 budget...",
        "[google-calendar] Team meeting: Weekly sync...",
    ]
    result = run_hermes_cycle(agent, summaries)
    assert result == "Found 3 connections between documents."
    agent.run_conversation.assert_called_once()
    call_args = agent.run_conversation.call_args[0][0]
    assert "Budget email" in call_args
    assert "Team meeting" in call_args


def test_run_hermes_cycle_exception():
    from mneia.agents.hermes_bridge import run_hermes_cycle

    agent = MagicMock()
    agent.run_conversation.side_effect = RuntimeError("LLM error")

    result = run_hermes_cycle(agent, ["[test] doc: content"])
    assert result is None


def test_create_hermes_agent():
    mock_ai_agent_cls = MagicMock()
    mock_ai_agent = MagicMock()
    mock_ai_agent_cls.return_value = mock_ai_agent

    mock_run_agent = MagicMock()
    mock_run_agent.AIAgent = mock_ai_agent_cls

    with patch.dict("sys.modules", {"run_agent": mock_run_agent}):
        from mneia.agents.hermes_bridge import create_hermes_agent

        config = MneiaConfig()
        store = MagicMock()
        graph = MagicMock()

        agent = create_hermes_agent(config, store, graph)
        mock_ai_agent_cls.assert_called_once()
        call_kwargs = mock_ai_agent_cls.call_args
        assert call_kwargs.kwargs.get("max_iterations") == 10
        assert "mneia's knowledge agent" in call_kwargs.kwargs.get("system_prompt", "")
