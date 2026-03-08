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

### Planned Connectors

These connectors are planned for future releases:

- **Apple Notes** — AppleScript-based reading from macOS Notes app
- **Asana** — API token access to projects and tasks
- **JIRA** — API token access to tickets
- **Confluence** — API token access to wiki pages
- **Notion** — Bearer token access to pages and databases
- **Zoom** — API key access to meeting recordings and details
- **Chrome History** — Local SQLite file reading
- **Audio Transcription** — System audio capture with whisper.cpp

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
