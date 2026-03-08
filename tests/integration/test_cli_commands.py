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
