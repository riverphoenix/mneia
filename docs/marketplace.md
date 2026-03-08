# Marketplace

The marketplace lets you discover and install third-party connectors from the community.

## Commands

### List Available Connectors

```bash
mneia marketplace list
```

Shows all connectors in the marketplace index, including built-in and third-party connectors, with installation status.

### Search Connectors

```bash
mneia marketplace search slack
mneia marketplace search "project management"
```

Searches by name, description, and tags. Results are ranked by relevance.

### Install a Connector

```bash
mneia marketplace install slack
```

Installs the connector package via pip, then enable it:

```bash
mneia connector enable slack
mneia connector setup slack
```

## How It Works

- The marketplace index is hosted at the mneia GitHub repository
- A local cache (`~/.mneia/marketplace_index.json`) is used with a 24-hour TTL
- When offline, falls back to cached index or lists built-in connectors
- Third-party connectors are pip packages named `mneia-connector-<name>`
- They register via Python entry points and are auto-discovered

## Building a Connector for the Marketplace

1. Create a Python package named `mneia-connector-yourservice`
2. Implement `BaseConnector` with a `manifest` class attribute
3. Register via entry points in `pyproject.toml`:

```toml
[project.entry-points."mneia.connectors"]
yourservice = "mneia_connector_yourservice:YourConnector"
```

4. Publish to PyPI
5. Submit a PR to the mneia repo to add your connector to `marketplace/index.json`

## MCP Integration

The marketplace is also accessible via the MCP server. AI tools like Claude Code can search for and discover connectors through the `mneia_marketplace_search` MCP tool. See [MCP Integration](mcp-integration.md) for details.

## Index Format

The marketplace index (`marketplace/index.json`) contains:

```json
{
  "version": "1.0.0",
  "connectors": [
    {
      "name": "slack",
      "display_name": "Slack",
      "description": "Read messages from Slack",
      "version": "0.1.0",
      "author": "mneia-community",
      "package_name": "mneia-connector-slack",
      "auth_type": "oauth2",
      "tags": ["messaging", "chat"],
      "homepage": "https://github.com/..."
    }
  ]
}
```
