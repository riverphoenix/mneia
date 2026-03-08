from __future__ import annotations

import platform

import pytest

from mneia.connectors.apple_notes import AppleNotesConnector


@pytest.fixture
def connector():
    return AppleNotesConnector()


def test_manifest():
    c = AppleNotesConnector()
    assert c.manifest.name == "apple-notes"
    assert c.manifest.auth_type == "applescript"


async def test_authenticate_non_darwin(connector, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_darwin(connector, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    result = await connector.authenticate({})
    assert result is True


async def test_authenticate_with_folders(connector, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    await connector.authenticate({"folders": "Work, Personal, Archive"})
    assert connector._folders == ["Work", "Personal", "Archive"]


def test_strip_html_basic():
    html = "<p>Hello <b>World</b></p><br/>New line"
    result = AppleNotesConnector._strip_html(html)
    assert "Hello" in result
    assert "World" in result
    assert "<b>" not in result
    assert "<p>" not in result


def test_strip_html_entities():
    html = "A &amp; B &lt;C&gt; D&nbsp;E"
    result = AppleNotesConnector._strip_html(html)
    assert "A & B" in result
    assert "<C>" in result


def test_strip_html_list_items():
    html = "<ul><li>First</li><li>Second</li></ul>"
    result = AppleNotesConnector._strip_html(html)
    assert "- First" in result
    assert "- Second" in result


def test_strip_html_empty():
    assert AppleNotesConnector._strip_html("") == ""


async def test_health_check_non_darwin(connector, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    result = await connector.health_check()
    assert result is False
