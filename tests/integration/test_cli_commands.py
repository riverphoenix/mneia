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
    output = result.output.lower()
    assert any(w in output for w in ["not running", "error", "started", "already running"])


def test_connector_stop_agent_no_daemon():
    result = runner.invoke(app, ["connector", "stop-agent", "obsidian"])
    assert result.exit_code == 0
    output = result.output.lower()
    assert any(w in output for w in ["not running", "error", "stopped", "not found"])


def test_connector_agents_no_daemon():
    result = runner.invoke(app, ["connector", "agents"])
    assert result.exit_code == 0


def test_logs_no_file():
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0


def test_stop_no_daemon():
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    output = result.output.lower()
    assert any(w in output for w in ["not running", "stopped", "sigterm", "stale"])


# --- clig.dev CLI standards ---


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "mneia v" in result.output


def test_version_json():
    result = runner.invoke(app, ["--json", "version"])
    import json

    data = json.loads(result.output)
    assert "version" in data


def test_connector_list_json():
    result = runner.invoke(app, ["--json", "connector", "list"])
    import json

    data = json.loads(result.output)
    assert "connectors" in data
    assert isinstance(data["connectors"], list)


def test_memory_stats_json():
    result = runner.invoke(app, ["--json", "memory", "stats"])
    import json

    data = json.loads(result.output)
    assert "total_documents" in data


def test_memory_search_json():
    result = runner.invoke(app, ["--json", "memory", "search", "xyznonexistent123"])
    import json

    data = json.loads(result.output)
    assert "results" in data
    assert isinstance(data["results"], list)


def test_quiet_suppresses_output():
    result = runner.invoke(app, ["--quiet", "version"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_no_color_flag():
    result = runner.invoke(app, ["--no-color", "version"])
    assert result.exit_code == 0
    assert "\x1b[" not in result.output
