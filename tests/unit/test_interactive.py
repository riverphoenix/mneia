from __future__ import annotations

import pytest

from mneia.interactive import InteractiveSession


@pytest.fixture
def session():
    s = InteractiveSession()
    return s


def test_detect_intent_start_daemon(session):
    intent, arg = session._detect_intent("start the daemon")
    assert intent == "start"


def test_detect_intent_stop_daemon(session):
    intent, arg = session._detect_intent("stop daemon")
    assert intent == "stop"


def test_detect_intent_stats(session):
    intent, arg = session._detect_intent("how many documents do I have")
    assert intent == "stats"


def test_detect_intent_recent(session):
    intent, arg = session._detect_intent("show me latest documents")
    assert intent == "recent"


def test_detect_intent_connectors(session):
    intent, arg = session._detect_intent("list connectors")
    assert intent == "connectors"


def test_detect_intent_status(session):
    intent, arg = session._detect_intent("show status")
    assert intent == "status"


def test_detect_intent_sync(session):
    intent, arg = session._detect_intent("sync obsidian")
    assert intent == "sync"
    assert arg == "obsidian"


def test_detect_intent_config(session):
    intent, arg = session._detect_intent("show config")
    assert intent == "config"


def test_detect_intent_graph(session):
    intent, arg = session._detect_intent("show knowledge graph")
    assert intent == "graph"


def test_detect_intent_entities(session):
    intent, arg = session._detect_intent("list entities")
    assert intent == "graph-entities"


def test_detect_intent_extract(session):
    intent, arg = session._detect_intent("run extraction")
    assert intent == "extract"


def test_detect_intent_context(session):
    intent, arg = session._detect_intent("generate context files")
    assert intent == "context"


def test_detect_intent_agents(session):
    intent, arg = session._detect_intent("list agents")
    assert intent == "agents"


def test_detect_intent_logs(session):
    intent, arg = session._detect_intent("show logs")
    assert intent == "logs"


def test_detect_intent_connector_start(session):
    intent, arg = session._detect_intent("start obsidian agent")
    assert intent == "connector-start"
    assert arg == "obsidian"


def test_detect_intent_connector_stop(session):
    intent, arg = session._detect_intent("stop obsidian agent")
    assert intent == "connector-stop"
    assert arg == "obsidian"


def test_detect_intent_none(session):
    intent, arg = session._detect_intent("what is the meaning of life")
    assert intent is None


def test_slash_commands_complete():
    from mneia.interactive import SLASH_COMMANDS

    expected = [
        "/help", "/status", "/search", "/ask", "/stats", "/recent",
        "/connectors", "/sync", "/connector-start", "/connector-stop",
        "/agents", "/extract", "/graph", "/graph-entities", "/graph-person",
        "/graph-topic", "/context", "/config", "/start", "/stop", "/logs",
        "/chat", "/clear", "/exit",
    ]
    for cmd in expected:
        assert cmd in SLASH_COMMANDS, f"Missing command: {cmd}"


def test_session_init(session):
    assert session.config is not None
    assert hasattr(session, "_ollama_available")


def test_handle_command_exit(session):
    result = session._handle_command("/exit")
    assert result is False


def test_handle_command_clear(session):
    result = session._handle_command("/clear")
    assert result is True


def test_cmd_ask_no_llm(session, capsys):
    session._ollama_available = False
    session._cmd_ask("test question")


def test_cmd_chat_no_llm(session, capsys):
    session._ollama_available = False
    session._cmd_chat()


def test_detect_source_hints_calendar():
    from mneia.interactive import InteractiveSession

    hints = InteractiveSession._detect_source_hints("what meetings do I have today")
    assert hints is not None
    assert "google-calendar" in hints


def test_detect_source_hints_email():
    from mneia.interactive import InteractiveSession

    hints = InteractiveSession._detect_source_hints("show me recent emails")
    assert hints is not None
    assert "gmail" in hints


def test_detect_source_hints_meeting():
    from mneia.interactive import InteractiveSession

    hints = InteractiveSession._detect_source_hints("what was said in the conversation")
    assert hints is not None
    assert "granola" in hints


def test_detect_source_hints_drive():
    from mneia.interactive import InteractiveSession

    hints = InteractiveSession._detect_source_hints("find the google doc about strategy")
    assert hints is not None
    assert "google-drive" in hints


def test_detect_source_hints_none():
    from mneia.interactive import InteractiveSession

    hints = InteractiveSession._detect_source_hints("tell me about quantum physics")
    assert hints is None


def test_detect_source_hints_multiple():
    from mneia.interactive import InteractiveSession

    hints = InteractiveSession._detect_source_hints(
        "what was discussed in the meeting transcript"
    )
    assert hints is not None
    assert "granola" in hints
