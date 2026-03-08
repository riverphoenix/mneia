from __future__ import annotations

from mneia.connectors.github import GitHubConnector
from mneia.connectors.linear import LinearConnector
from mneia.connectors.slack import SlackConnector
from mneia.connectors.todoist import TodoistConnector


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


def test_linear_manifest():
    c = LinearConnector()
    assert c.manifest.name == "linear"
    assert "linear_api_key" in c.manifest.required_config


async def test_linear_authenticate():
    c = LinearConnector()
    result = await c.authenticate({
        "linear_api_key": "lin_test",
        "team_ids": "team1, team2",
    })
    assert result is True
    assert len(c._team_ids) == 2


def test_linear_issue_to_document():
    c = LinearConnector()
    issue = {
        "id": "issue-1",
        "identifier": "ENG-42",
        "title": "Fix login",
        "description": "Login is broken",
        "state": {"name": "In Progress"},
        "assignee": {"name": "Charlie"},
        "priority": 2,
        "labels": {"nodes": [{"name": "bug"}]},
        "updatedAt": "2024-01-01T00:00:00Z",
        "url": "https://linear.app/team/ENG-42",
        "team": {"name": "Engineering"},
    }
    doc = c._issue_to_document(issue)
    assert doc is not None
    assert doc.source == "linear"
    assert "ENG-42" in doc.title
    assert "Charlie" in doc.participants
    assert doc.metadata["priority"] == 2


def test_todoist_manifest():
    c = TodoistConnector()
    assert c.manifest.name == "todoist"
    assert "todoist_api_token" in c.manifest.required_config


async def test_todoist_authenticate():
    c = TodoistConnector()
    result = await c.authenticate({"todoist_api_token": "test_token"})
    assert result is True


async def test_todoist_authenticate_no_token():
    c = TodoistConnector()
    result = await c.authenticate({})
    assert result is False


def test_todoist_task_to_document():
    c = TodoistConnector()
    task = {
        "id": "123",
        "content": "Buy groceries",
        "description": "Milk, eggs, bread",
        "priority": 3,
        "project_id": "proj1",
        "labels": ["shopping"],
        "due": {"string": "tomorrow", "date": "2024-01-02"},
        "created_at": "2024-01-01T00:00:00Z",
        "url": "https://todoist.com/task/123",
        "is_completed": False,
    }
    doc = c._task_to_document(task, {"proj1": "Personal"})
    assert doc is not None
    assert doc.source == "todoist"
    assert doc.title == "Buy groceries"
    assert "Personal" in doc.content
    assert "shopping" in doc.content


def test_todoist_task_no_id():
    c = TodoistConnector()
    doc = c._task_to_document({"content": "test"}, {})
    assert doc is None


def test_all_connectors_registered():
    from mneia.connectors import get_available_connectors

    manifests = get_available_connectors()
    names = {m.name for m in manifests}
    assert "slack" in names
    assert "github" in names
    assert "linear" in names
    assert "todoist" in names
