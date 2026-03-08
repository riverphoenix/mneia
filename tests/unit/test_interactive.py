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
        "/clear", "/exit",
    ]
    for cmd in expected:
        assert cmd in SLASH_COMMANDS, f"Missing command: {cmd}"
