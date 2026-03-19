from __future__ import annotations

import httpx

PROVIDER_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-20241022",
    ],
    "openai": [
        "o3",
        "o3-mini",
        "o4-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
    ],
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ],
}

PROVIDER_DISPLAY: dict[str, str] = {
    "ollama": "Ollama (local, free)",
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (ChatGPT)",
    "google": "Google (Gemini)",
}

EMBEDDING_MODELS: dict[str, str] = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
    "google": "text-embedding-004",
    "anthropic": "nomic-embed-text",
}

CONNECTOR_HELP: dict[str, dict[str, str]] = {
    "obsidian": {
        "description": "Reads markdown notes from an Obsidian vault on your local filesystem.",
        "prerequisites": "An Obsidian vault directory with .md files.",
        "setup_help": "You'll need the full path to your Obsidian vault folder.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Your notes will sync automatically via file watching.\n"
            "3. Run mneia extract to build your knowledge graph.\n"
            "4. Try: mneia ask 'what are my recent notes about?'"
        ),
    },
    "gmail": {
        "description": "Reads emails from Gmail using Google API.",
        "prerequisites": (
            "A Google Cloud project with Gmail API enabled.\n"
            "  Download OAuth credentials JSON from Google Cloud Console."
        ),
        "setup_help": "You'll need your Google OAuth credentials file path.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Emails will be polled every 5 minutes.\n"
            "3. Run mneia extract to extract people and topics."
        ),
    },
    "google_calendar": {
        "description": "Reads events from Google Calendar.",
        "prerequisites": "A Google Cloud project with Calendar API enabled.",
        "setup_help": "You'll need your Google OAuth credentials file path.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Calendar events sync every 5 minutes.\n"
            "3. Try: mneia ask 'what meetings do I have this week?'"
        ),
    },
    "google_drive": {
        "description": "Reads documents from Google Drive.",
        "prerequisites": "A Google Cloud project with Drive API enabled.",
        "setup_help": "You'll need your Google OAuth credentials file path.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Documents sync periodically.\n"
            "3. Try: mneia ask 'what documents have I worked on recently?'"
        ),
    },
    "slack": {
        "description": "Reads messages from Slack channels using a Bot token.",
        "prerequisites": (
            "A Slack App with Bot Token.\n"
            "  Create at: https://api.slack.com/apps\n"
            "  Required scopes: channels:history, channels:read"
        ),
        "setup_help": "You'll need your Slack Bot User OAuth Token (xoxb-...).",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Messages polled every 5 minutes.\n"
            "3. Try: mneia ask 'what was discussed in slack today?'"
        ),
    },
    "github": {
        "description": "Reads issues, PRs, and commits from GitHub repos.",
        "prerequisites": "A GitHub personal access token (classic or fine-grained).",
        "setup_help": "You'll need your GitHub token and repository name (owner/repo).",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Issues and PRs sync periodically.\n"
            "3. Try: mneia ask 'what PRs were merged recently?'"
        ),
    },
    "notion": {
        "description": "Reads pages from Notion workspaces.",
        "prerequisites": (
            "A Notion integration token.\n"
            "  Create at: https://www.notion.so/my-integrations"
        ),
        "setup_help": "You'll need your Notion integration token.",
        "next_steps": (
            "1. Share pages/databases with your integration in Notion.\n"
            "2. Start the daemon: mneia start -d\n"
            "3. Pages sync periodically."
        ),
    },
    "linear": {
        "description": "Reads issues from Linear project management.",
        "prerequisites": (
            "A Linear API key.\n"
            "  Create at: Linear Settings > API"
        ),
        "setup_help": "You'll need your Linear API key.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Issues sync periodically.\n"
            "3. Try: mneia ask 'what are my open linear issues?'"
        ),
    },
    "todoist": {
        "description": "Reads tasks from Todoist.",
        "prerequisites": (
            "A Todoist API token.\n"
            "  Find at: Todoist Settings > Integrations > Developer"
        ),
        "setup_help": "You'll need your Todoist API token.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Tasks sync periodically.\n"
            "3. Try: mneia ask 'what tasks are due today?'"
        ),
    },
    "asana": {
        "description": "Reads tasks from Asana projects.",
        "prerequisites": "An Asana personal access token.",
        "setup_help": "You'll need your Asana PAT and project GID.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Tasks sync periodically."
        ),
    },
    "confluence": {
        "description": "Reads pages from Atlassian Confluence.",
        "prerequisites": "Confluence URL, email, and API token.",
        "setup_help": "You'll need your Confluence URL, email, and API token.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Pages sync periodically."
        ),
    },
    "jira": {
        "description": "Reads issues from Atlassian Jira.",
        "prerequisites": "Jira URL, email, and API token.",
        "setup_help": "You'll need your Jira URL, email, and API token.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Issues sync periodically."
        ),
    },
    "zoom": {
        "description": "Reads meeting recordings and transcripts from Zoom.",
        "prerequisites": "Zoom Server-to-Server OAuth credentials.",
        "setup_help": "You'll need Account ID, Client ID, and Client Secret from Zoom Marketplace.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Recordings sync periodically."
        ),
    },
    "chrome_history": {
        "description": "Reads browsing history from Chrome.",
        "prerequisites": "Chrome must be installed. History DB is read locally.",
        "setup_help": "No credentials needed. Optionally filter by domain.",
        "next_steps": (
            "1. Run mneia connector sync chrome_history for a one-time sync.\n"
            "2. Start the daemon for continuous sync."
        ),
    },
    "audio_transcription": {
        "description": "Transcribes audio files using Whisper.",
        "prerequisites": "Install audio extras: pip install 'mneia[audio]'",
        "setup_help": "You'll need the path to your audio files directory.",
        "next_steps": (
            "1. Place audio files in the configured directory.\n"
            "2. Run mneia connector sync audio_transcription."
        ),
    },
    "local_folders": {
        "description": "Scan and monitor local directories for text, code, and PDF files.",
        "prerequisites": "One or more local directories to scan. BM25 search is included.",
        "setup_help": "You'll provide folder paths to scan. Optionally configure file extensions and exclusion patterns.",
        "next_steps": (
            "1. Start the daemon: mneia start -d\n"
            "2. Documents will be indexed automatically with BM25 search."
        ),
    },
    "granola": {
        "description": "Read meeting notes from Granola.",
        "prerequisites": "Granola app installed with notes exported as markdown.",
        "setup_help": "Point to the directory where Granola saves meeting notes.",
        "next_steps": (
            "1. Start the daemon with: mneia start\n"
            "2. Meeting notes are synced automatically."
        ),
    },
    "apple_notes": {
        "description": "Reads notes from Apple Notes on macOS.",
        "prerequisites": "macOS with Apple Notes app.",
        "setup_help": "No credentials needed.",
        "next_steps": (
            "1. Run mneia connector sync apple_notes.\n"
            "2. Notes are read from the local database."
        ),
    },
}


def get_connector_help(name: str) -> dict[str, str] | None:
    return CONNECTOR_HELP.get(name)


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return sorted(m["name"] for m in models)
    except Exception:
        pass
    return []


def list_openai_models(api_key: str) -> list[str]:
    try:
        resp = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            chat_prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt-")
            chat_models = [
                m["id"] for m in models
                if any(m["id"].startswith(p) for p in chat_prefixes)
                and "realtime" not in m["id"]
                and "audio" not in m["id"]
                and "search" not in m["id"]
            ]
            return sorted(chat_models, reverse=True)
    except Exception:
        pass
    return []


def get_models_for_provider(
    provider: str,
    ollama_url: str = "",
    api_key: str = "",
) -> list[str]:
    if provider == "ollama":
        return list_ollama_models(ollama_url or "http://localhost:11434")
    if provider == "openai" and api_key:
        live = list_openai_models(api_key)
        if live:
            return live
    return PROVIDER_MODELS.get(provider, [])
