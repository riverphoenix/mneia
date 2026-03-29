from __future__ import annotations

from mneia.connectors.github import GitHubConnector
from mneia.connectors.slack import SlackConnector


def test_slack_manifest():
    c = SlackConnector()
    assert c.manifest.name == "slack"
    assert c.manifest.auth_type == "bot_token"


async def test_slack_authenticate():
    c = SlackConnector()
    result = await c.authenticate({"slack_token": "xoxb-test"})
    assert result is True
    assert c._token == "xoxb-test"


async def test_slack_authenticate_no_token():
    c = SlackConnector()
    result = await c.authenticate({})
    assert result is False


def test_slack_message_to_document():
    c = SlackConnector()
    msg = {
        "text": "Hello world",
        "ts": "1700000000.000000",
        "user": "U123",
    }
    doc = c._message_to_document(msg, "C456")
    assert doc is not None
    assert doc.source == "slack"
    assert doc.content == "Hello world"
    assert "U123" in doc.participants


def test_slack_message_empty_text():
    c = SlackConnector()
    msg = {"text": "", "ts": "123", "user": "U1"}
    doc = c._message_to_document(msg, "C1")
    assert doc is None


def test_github_manifest():
    c = GitHubConnector()
    assert c.manifest.name == "github"
    assert "github_token" in c.manifest.required_config


async def test_github_authenticate():
    c = GitHubConnector()
    result = await c.authenticate({
        "github_token": "ghp_test",
        "repos": "owner/repo1, owner/repo2",
    })
    assert result is True
    assert len(c._repos) == 2


def test_github_issue_to_document():
    c = GitHubConnector()
    item = {
        "number": 42,
        "title": "Bug fix",
        "body": "Fix the bug",
        "state": "open",
        "user": {"login": "alice"},
        "labels": [{"name": "bug"}],
        "updated_at": "2024-01-01T00:00:00Z",
        "html_url": "https://github.com/owner/repo/issues/42",
    }
    doc = c._issue_to_document(item, "owner/repo")
    assert doc is not None
    assert doc.source == "github"
    assert doc.content_type == "issue"
    assert "Bug fix" in doc.title
    assert "alice" in doc.participants


def test_github_pr_to_document():
    c = GitHubConnector()
    pr = {
        "number": 10,
        "title": "Add feature",
        "body": "New feature impl",
        "state": "closed",
        "merged_at": "2024-01-02T00:00:00Z",
        "user": {"login": "bob"},
        "updated_at": "2024-01-02T00:00:00Z",
        "html_url": "https://github.com/owner/repo/pull/10",
    }
    doc = c._pr_to_document(pr, "owner/repo")
    assert doc is not None
    assert doc.content_type == "pull_request"
    assert "merged" in doc.content


def test_all_connectors_registered():
    from mneia.connectors import get_available_connectors

    manifests = get_available_connectors()
    names = {m.name for m in manifests}
    assert "slack" in names
    assert "github" in names
    assert "confluence" in names
    assert "notion" in names
    assert "google-drive" in names
    assert "apple-notes" in names
    assert "chrome-history" in names
