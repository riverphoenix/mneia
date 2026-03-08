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

### Planned Connectors

These connectors are planned for future releases:

- **Apple Notes** — AppleScript-based reading from macOS Notes app
- **Google Calendar** — OAuth2 readonly access to calendar events
- **Gmail** — OAuth2 readonly access to email
- **Google Drive** — OAuth2 readonly access to files, Docs, Sheets, Slides
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
