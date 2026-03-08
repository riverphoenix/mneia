from __future__ import annotations

from typer.testing import CliRunner

from mneia.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "mneia v" in result.output


def test_config_show():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "ollama" in result.output


def test_connector_list():
    result = runner.invoke(app, ["connector", "list"])
    assert result.exit_code == 0
    assert "obsidian" in result.output.lower()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mneia" in result.output.lower()


def test_memory_stats():
    result = runner.invoke(app, ["memory", "stats"])
    assert result.exit_code == 0
    assert "Total documents" in result.output or "documents" in result.output.lower()


def test_memory_search_no_results():
    result = runner.invoke(app, ["memory", "search", "xyznonexistent123"])
    assert result.exit_code == 0
    assert "No results" in result.output


def test_graph_show():
    result = runner.invoke(app, ["graph", "show"])
    assert result.exit_code == 0
    assert "entities" in result.output.lower() or "Knowledge Graph" in result.output


def test_graph_entities():
    result = runner.invoke(app, ["graph", "entities"])
    assert result.exit_code == 0


def test_graph_export():
    result = runner.invoke(app, ["graph", "export"])
    assert result.exit_code == 0


def test_context_show():
    result = runner.invoke(app, ["context", "show"])
    assert result.exit_code == 0


def test_connector_start_agent_no_daemon():
    result = runner.invoke(app, ["connector", "start-agent", "obsidian"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower() or "error" in result.output.lower() or "Error" in result.output or "Daemon" in result.output


def test_connector_stop_agent_no_daemon():
    result = runner.invoke(app, ["connector", "stop-agent", "obsidian"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower() or "error" in result.output.lower() or "Daemon" in result.output


def test_connector_agents_no_daemon():
    result = runner.invoke(app, ["connector", "agents"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower() or "Daemon" in result.output


def test_logs_no_file():
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0


def test_stop_no_daemon():
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower()
