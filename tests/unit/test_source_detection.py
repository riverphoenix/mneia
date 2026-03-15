from __future__ import annotations

import pytest

from mneia.interactive import InteractiveSession


def test_format_source_tag_calendar():
    tag = InteractiveSession._format_source_tag("google-calendar")
    assert "bright_green" in tag
    assert "google-calendar" in tag


def test_format_source_tag_gmail():
    tag = InteractiveSession._format_source_tag("gmail")
    assert "bright_blue" in tag


def test_format_source_tag_drive():
    tag = InteractiveSession._format_source_tag("google-drive")
    assert "bright_yellow" in tag


def test_format_source_tag_granola():
    tag = InteractiveSession._format_source_tag("granola")
    assert "bright_magenta" in tag


def test_format_source_tag_obsidian():
    tag = InteractiveSession._format_source_tag("obsidian")
    assert "bright_cyan" in tag


def test_format_source_tag_knowledge_agent():
    tag = InteractiveSession._format_source_tag("knowledge-agent")
    assert "bright_red" in tag


def test_format_source_tag_unknown():
    tag = InteractiveSession._format_source_tag("unknown-source")
    assert "dim" in tag


def test_cli_detect_source_hints_calendar():
    from mneia.cli import _detect_source_hints
    hints = _detect_source_hints("what meetings do I have")
    assert hints is not None
    assert "google-calendar" in hints


def test_cli_detect_source_hints_email():
    from mneia.cli import _detect_source_hints
    hints = _detect_source_hints("show me emails from john")
    assert hints is not None
    assert "gmail" in hints


def test_cli_detect_source_hints_meeting():
    from mneia.cli import _detect_source_hints
    hints = _detect_source_hints("what was said in the conversation")
    assert hints is not None
    assert "granola" in hints


def test_cli_detect_source_hints_drive():
    from mneia.cli import _detect_source_hints
    hints = _detect_source_hints("find the google doc")
    assert hints is not None
    assert "google-drive" in hints


def test_cli_detect_source_hints_none():
    from mneia.cli import _detect_source_hints
    hints = _detect_source_hints("what is the meaning of life")
    assert hints is None


def test_cli_detect_source_hints_multiple():
    from mneia.cli import _detect_source_hints
    hints = _detect_source_hints("meeting transcript from the conversation")
    assert hints is not None
    assert "granola" in hints


def test_build_system_prompt_includes_date():
    prompt = InteractiveSession._build_system_prompt()
    assert "Current date and time:" in prompt
    assert "mneia" in prompt
    assert "memory" in prompt


def test_build_system_prompt_includes_commands():
    commands = {"/test": {"desc": "Test command", "alias": ""}}
    prompt = InteractiveSession._build_system_prompt(
        include_commands=True, commands_dict=commands,
    )
    assert "COMMAND:" in prompt
    assert "/test" in prompt


def test_build_system_prompt_no_commands():
    prompt = InteractiveSession._build_system_prompt()
    assert "COMMAND:" not in prompt


def test_find_graph_node_exact_match():
    from unittest.mock import MagicMock
    import networkx as nx

    graph = MagicMock()
    graph._graph = nx.DiGraph()
    graph._graph.add_node("topic:budget", name="Budget", entity_type="topic")

    node_id = InteractiveSession._find_graph_node(graph, "Budget", "topic")
    assert node_id == "topic:budget"


def test_find_graph_node_name_search():
    from unittest.mock import MagicMock
    import networkx as nx

    graph = MagicMock()
    graph._graph = nx.DiGraph()
    graph._graph.add_node("project:budget", name="Budget", entity_type="project")

    node_id = InteractiveSession._find_graph_node(graph, "Budget", "topic")
    assert node_id == "project:budget"


def test_find_graph_node_partial_match():
    from unittest.mock import MagicMock
    import networkx as nx

    graph = MagicMock()
    graph._graph = nx.DiGraph()
    graph._graph.add_node("topic:q1-budget", name="Q1 Budget", entity_type="topic")

    node_id = InteractiveSession._find_graph_node(graph, "budget", "topic")
    assert node_id == "topic:q1-budget"


def test_find_graph_node_not_found():
    from unittest.mock import MagicMock
    import networkx as nx

    graph = MagicMock()
    graph._graph = nx.DiGraph()

    node_id = InteractiveSession._find_graph_node(graph, "nonexistent")
    assert node_id is None