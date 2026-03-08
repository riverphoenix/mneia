# Connectors

Connectors are the data sources that mneia reads from to build your personal knowledge base. All connectors are **read-only** — they never modify your data.

## Available Connectors

### Obsidian (Available)

Reads markdown files from an Obsidian vault.

**Auth:** Local filesystem access
**Setup:**
```bash
mneia connector enable obsidian
mneia connector setup obsidian   # Prompts for vault path
mneia connector sync obsidian    # Ingest documents
```

**Features:**
- Reads all `.md` files recursively
- Parses YAML frontmatter (title, tags, date)
- Extracts headings structure
- Detects `#tags` and `[[wikilinks]]`
- Excludes `.obsidian/` and other hidden directories
- Supports configurable exclude folders
- Watches for file changes when running as daemon

### Google Calendar (Available)

Reads events from Google Calendar via OAuth2.

**Auth:** OAuth2 (readonly)
**Setup:**
```bash
mneia connector enable google-calendar
mneia connector setup google-calendar   # OAuth2 flow opens browser
mneia connector sync google-calendar
```

**Features:**
- Fetches events from one or more calendars
- Extracts attendees, organizer, location, meeting links
- Supports configurable lookback period
- Detects recurring events and conference data

### Gmail (Available)

Reads emails from Gmail via OAuth2.

**Auth:** OAuth2 (readonly)
**Setup:**
```bash
mneia connector enable gmail
mneia connector setup gmail
mneia connector sync gmail
```

**Features:**
- Fetches emails from specified labels (default: INBOX)
- Extracts sender, recipients, CC, subject, body
- Handles multipart emails (plain text and HTML)
- Supports Gmail search query filters
- Configurable max results per sync

### Google Drive (Available)

Reads files from Google Drive including Docs, Sheets, and Slides.

**Auth:** OAuth2 (readonly)
**Setup:**
```bash
mneia connector enable google-drive
mneia connector setup google-drive
mneia connector sync google-drive
```

**Features:**
- Reads Google Docs (exported as plain text)
- Reads Google Sheets (exported as CSV)
- Reads Google Slides (exported as plain text)
- Reads plain text, markdown, CSV, HTML, and JSON files
- Supports folder ID filtering
- Includes shared drives
- Truncates large files (>50KB) to prevent memory issues

### Apple Notes (Available)

Reads notes from the macOS Apple Notes app via AppleScript.

**Auth:** AppleScript (macOS only)
**Setup:**
```bash
mneia connector enable apple-notes
mneia connector setup apple-notes
mneia connector sync apple-notes
```

**Features:**
- Reads all notes via AppleScript
- Strips HTML formatting from note bodies
- Supports folder filtering
- Extracts modification dates and folder metadata

### Asana (Available)

Reads tasks and projects from Asana.

**Auth:** API token (Personal Access Token)
**Setup:**
```bash
mneia connector enable asana
mneia connector setup asana
mneia connector sync asana
```

**Features:**
- Fetches tasks from specific projects or entire workspace
- Extracts assignee, due date, status, tags
- Supports modified_since filtering
- Auto-detects workspace if not specified

### JIRA (Available)

Reads issues from Atlassian JIRA.

**Auth:** API token (email + token)
**Setup:**
```bash
mneia connector enable jira
mneia connector setup jira
mneia connector sync jira
```

**Features:**
- Fetches issues via JQL queries
- Extracts Atlassian Document Format (ADF) descriptions
- Includes last 5 comments per issue
- Extracts assignee, reporter, status, priority, labels

### Confluence (Available)

Reads pages from Atlassian Confluence.

**Auth:** API token (email + token)
**Setup:**
```bash
mneia connector enable confluence
mneia connector setup confluence
mneia connector sync confluence
```

**Features:**
- Searches pages via CQL
- Strips HTML from storage format body
- Supports space key filtering
- Extracts page hierarchy (ancestors)

### Notion (Available)

Reads pages and databases from Notion.

**Auth:** Bearer token (Integration token)
**Setup:**
```bash
mneia connector enable notion
mneia connector setup notion
mneia connector sync notion
```

**Features:**
- Fetches pages via search API with pagination
- Converts blocks to markdown (paragraphs, headings, lists, code, to-do, dividers)
- Supports database ID filtering
- Extracts page metadata, participants, parent info

### Zoom (Available)

Reads meeting recordings and transcripts from Zoom.

**Auth:** OAuth2 (Server-to-Server app)
**Setup:**
```bash
mneia connector enable zoom
mneia connector setup zoom
mneia connector sync zoom
```

**Features:**
- Fetches meeting recordings list
- Downloads and parses VTT transcripts
- Extracts meeting topic, duration, host
- Supports date range filtering

### Chrome History (Available)

Reads browsing history from Google Chrome.

**Auth:** Local filesystem (read-only copy)
**Setup:**
```bash
mneia connector enable chrome-history
mneia connector setup chrome-history
mneia connector sync chrome-history
```

**Features:**
- Copies Chrome history database (read-only, non-blocking)
- Extracts URLs, titles, visit counts
- Auto-detects Chrome profile path on macOS, Linux, Windows
- Supports custom history file path

### Audio Transcription (Available)

Transcribes audio files using whisper.cpp or faster-whisper.

**Auth:** Local filesystem
**Setup:**
```bash
pip install faster-whisper  # or: brew install whisper-cpp
mneia connector enable audio-transcription
mneia connector setup audio-transcription
mneia connector sync audio-transcription
```

**Features:**
- Supports MP3, WAV, M4A, OGG, FLAC, WebM, MP4
- Auto-detects backend (faster-whisper or whisper-cpp)
- Configurable model size (tiny/base/small/medium/large)
- Configurable language

## Agent Management

Each enabled connector gets a `ListenerAgent` that runs inside the daemon. You can manage individual agents:

```bash
mneia connector start-agent obsidian   # Start obsidian's listener
mneia connector stop-agent obsidian    # Stop without stopping daemon
mneia connector agents                 # List running agents
```

In interactive mode:
```
/connector-start obsidian
/connector-stop obsidian
/agents
```

## Building Custom Connectors

Implement the `BaseConnector` interface:

```python
from mneia.core.connector import BaseConnector, ConnectorManifest, RawDocument

class MyConnector(BaseConnector):
    MANIFEST = ConnectorManifest(
        name="myservice",
        display_name="My Service",
        version="1.0.0",
        description="Read data from My Service",
        auth_type="api_key",
        mode="poll",
        poll_interval_seconds=300,
    )

    async def authenticate(self, settings: dict) -> bool:
        # Validate credentials
        return True

    async def fetch(self, since: str | None = None) -> list[RawDocument]:
        # Fetch documents since checkpoint
        return [...]

    async def health_check(self) -> bool:
        return True

    def interactive_setup(self) -> dict:
        # Return settings dict from user input
        return {"api_key": "..."}
```

### Publishing

Package as `mneia-connector-myservice` and register via entry points:

```toml
[project.entry-points."mneia.connectors"]
myservice = "mneia_connector_myservice:MyConnector"
```

Users install with:
```bash
pip install mneia-connector-myservice
```

The connector is automatically discovered on next startup.
