from __future__ import annotations

from mneia.connectors.github import GitHubConnector


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


def test_github_detect_token_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_env_token")
    token, source = GitHubConnector._detect_github_token()
    assert token == "ghp_env_token"
    assert "$GITHUB_TOKEN" in source


def test_github_detect_token_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    token, source = GitHubConnector._detect_github_token()
    # May or may not find gh CLI config — just check types
    assert isinstance(token, str)
    assert isinstance(source, str)


def test_all_connectors_registered():
    from mneia.connectors import get_available_connectors

    manifests = get_available_connectors()
    names = {m.name for m in manifests}
    assert "github" in names
    assert "google-drive" in names
    assert "apple-notes" in names
    assert "chrome-history" in names
    assert "obsidian" in names
    assert "gmail" in names
    # Removed connectors must not appear
    assert "slack" not in names
    assert "jira" not in names
    assert "linear" not in names
    assert "todoist" not in names
    assert "zoom" not in names
    assert "asana" not in names
    assert "confluence" not in names
    assert "notion" not in names
