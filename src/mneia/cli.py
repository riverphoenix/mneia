from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mneia import __version__
from mneia.config import MneiaConfig, ensure_dirs

app = typer.Typer(
    name="mneia",
    help="Autonomous multi-agent personal knowledge system",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

BANNER = r"""
                         _
  _ __ ___  _ __   ___  (_) __ _
 | '_ ` _ \| '_ \ / _ \ | |/ _` |
 | | | | | | | | |  __/ | | (_| |
 |_| |_| |_|_| |_|\___| |_|\__,_|

"""


def _print_banner() -> None:
    console.print(Text(BANNER, style="bold cyan"))
    console.print(f"  v{__version__} — your personal knowledge agent\n", style="dim")


# --- Top-level commands ---


@app.command()
def version() -> None:
    """Show mneia version."""
    console.print(f"mneia v{__version__}")


@app.command()
def start(
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
    connectors: Optional[str] = typer.Option(
        None, "--connectors", "-c", help="Comma-separated connector names"
    ),
) -> None:
    """Start the mneia knowledge daemon."""
    ensure_dirs()
    _print_banner()
    config = MneiaConfig.load()

    connector_filter = connectors.split(",") if connectors else None

    from mneia.core.lifecycle import AgentManager

    manager = AgentManager(config, connector_filter=connector_filter)

    if detach:
        console.print("[yellow]Background mode not yet implemented. Running in foreground.[/yellow]")

    console.print("[green]Starting mneia...[/green]")
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def stop() -> None:
    """Stop the mneia daemon."""
    console.print("[yellow]Sending stop signal...[/yellow]")
    from mneia.core.lifecycle import send_command

    try:
        asyncio.run(send_command("stop"))
        console.print("[green]mneia stopped.[/green]")
    except ConnectionRefusedError:
        console.print("[red]mneia is not running.[/red]")


@app.command()
def status() -> None:
    """Show daemon status, agent states, and queue depth."""
    from mneia.core.lifecycle import send_command

    try:
        result = asyncio.run(send_command("status"))
        if result.get("running"):
            console.print(Panel("[green]mneia is running[/green]", title="Status"))
            table = Table(title="Agents")
            table.add_column("Agent", style="cyan")
            table.add_column("State", style="green")
            table.add_column("Docs Processed", justify="right")
            for agent in result.get("agents", []):
                table.add_row(agent["name"], agent["state"], str(agent.get("docs", 0)))
            console.print(table)
        else:
            console.print("[yellow]mneia is not running.[/yellow]")
    except (ConnectionRefusedError, FileNotFoundError):
        console.print("[yellow]mneia is not running.[/yellow]")


# --- Config commands ---

config_app = typer.Typer(help="Manage mneia configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    config = MneiaConfig.load()
    console.print_json(config.model_dump_json(indent=2))


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a configuration value (dot-separated key path)."""
    config = MneiaConfig.load()
    try:
        config.set_value(key, value)
        console.print(f"[green]Set {key} = {value}[/green]")
    except (AttributeError, KeyError) as e:
        console.print(f"[red]Invalid key: {key} ({e})[/red]")
        raise typer.Exit(1)


@config_app.command("setup")
def config_setup() -> None:
    """Interactive setup wizard."""
    ensure_dirs()
    _print_banner()
    config = MneiaConfig.load()

    console.print(Panel("Welcome to mneia setup!", title="Setup Wizard"))

    provider = typer.prompt(
        "LLM provider (ollama/anthropic/openai)",
        default=config.llm.provider,
    )
    config.llm.provider = provider

    if provider == "ollama":
        model = typer.prompt("Ollama model for extraction", default=config.llm.model)
        config.llm.model = model
        embed = typer.prompt("Ollama embedding model", default=config.llm.embedding_model)
        config.llm.embedding_model = embed
        url = typer.prompt("Ollama base URL", default=config.llm.ollama_base_url)
        config.llm.ollama_base_url = url
    elif provider == "anthropic":
        key = typer.prompt("Anthropic API key", hide_input=True)
        config.llm.anthropic_api_key = key
        config.llm.model = "claude-sonnet-4-20250514"
    elif provider == "openai":
        key = typer.prompt("OpenAI API key", hide_input=True)
        config.llm.openai_api_key = key
        config.llm.model = "gpt-4o-mini"

    context_dir = typer.prompt(
        "Context output directory",
        default=config.context_output_dir,
    )
    config.context_output_dir = context_dir

    config.save()
    console.print("\n[green]Configuration saved![/green]")
    console.print("Next: enable a connector with [cyan]mneia connector enable <name>[/cyan]")


@config_app.command("reset")
def config_reset() -> None:
    """Reset configuration to defaults."""
    if typer.confirm("Reset all configuration to defaults?"):
        config = MneiaConfig()
        config.save()
        console.print("[green]Configuration reset.[/green]")


# --- Connector commands ---

connector_app = typer.Typer(help="Manage data connectors")
app.add_typer(connector_app, name="connector")


@connector_app.command("list")
def connector_list() -> None:
    """List available connectors and their status."""
    config = MneiaConfig.load()
    from mneia.connectors import get_available_connectors

    available = get_available_connectors()

    table = Table(title="Connectors")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Status", style="green")
    table.add_column("Auth")

    for manifest in available:
        conn_config = config.connectors.get(manifest.name)
        status = "[green]enabled[/green]" if conn_config and conn_config.enabled else "[dim]disabled[/dim]"
        table.add_row(manifest.name, manifest.display_name, status, manifest.auth_type)

    console.print(table)


@connector_app.command("enable")
def connector_enable(name: str) -> None:
    """Enable a connector."""
    config = MneiaConfig.load()
    from mneia.connectors import get_connector_manifest

    manifest = get_connector_manifest(name)
    if not manifest:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    if name not in config.connectors:
        from mneia.config import ConnectorConfig

        config.connectors[name] = ConnectorConfig(
            enabled=True,
            poll_interval_seconds=manifest.poll_interval_seconds,
        )
    else:
        config.connectors[name].enabled = True

    config.save()
    console.print(f"[green]Enabled connector: {name}[/green]")
    console.print(f"Run [cyan]mneia connector setup {name}[/cyan] to configure it.")


@connector_app.command("disable")
def connector_disable(name: str) -> None:
    """Disable a connector."""
    config = MneiaConfig.load()
    if name in config.connectors:
        config.connectors[name].enabled = False
        config.save()
        console.print(f"[yellow]Disabled connector: {name}[/yellow]")
    else:
        console.print(f"[red]Connector not configured: {name}[/red]")


@connector_app.command("setup")
def connector_setup(name: str) -> None:
    """Run interactive setup for a connector."""
    config = MneiaConfig.load()
    from mneia.connectors import create_connector

    connector = create_connector(name)
    if not connector:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    console.print(Panel(f"Setting up [cyan]{name}[/cyan]", title="Connector Setup"))

    if name not in config.connectors:
        from mneia.config import ConnectorConfig

        config.connectors[name] = ConnectorConfig(enabled=True)

    settings = connector.interactive_setup()
    config.connectors[name].settings = settings
    config.connectors[name].enabled = True
    config.save()
    console.print(f"[green]{name} configured and enabled![/green]")


@connector_app.command("sync")
def connector_sync(name: str) -> None:
    """Trigger immediate sync for a connector."""
    config = MneiaConfig.load()
    conn_config = config.connectors.get(name)
    if not conn_config or not conn_config.enabled:
        console.print(f"[red]Connector {name} is not enabled.[/red]")
        raise typer.Exit(1)

    from mneia.connectors import create_connector
    from mneia.pipeline.ingest import ingest_connector

    connector = create_connector(name)
    if not connector:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Syncing {name}...[/cyan]")
    result = asyncio.run(ingest_connector(connector, conn_config, config))
    console.print(f"[green]Synced {result.documents_ingested} documents from {name}[/green]")

    if conn_config.last_checkpoint != result.checkpoint:
        conn_config.last_checkpoint = result.checkpoint
        config.save()


# --- Memory commands ---

memory_app = typer.Typer(help="Browse and search your knowledge")
app.add_typer(memory_app, name="memory")


@memory_app.command("stats")
def memory_stats() -> None:
    """Show memory statistics."""
    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    stats = asyncio.run(store.get_stats())

    table = Table(title="Memory Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total documents", str(stats.get("total_documents", 0)))
    table.add_row("Total entities", str(stats.get("total_entities", 0)))
    table.add_row("Total associations", str(stats.get("total_associations", 0)))

    if "by_source" in stats:
        table.add_section()
        for source, count in stats["by_source"].items():
            table.add_row(f"  {source}", str(count))

    console.print(table)


@memory_app.command("search")
def memory_search(
    query: str,
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Full-text search across all stored knowledge."""
    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    results = asyncio.run(store.search(query, limit=limit))

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for doc in results:
        panel_content = doc.content[:500]
        if len(doc.content) > 500:
            panel_content += "..."
        console.print(
            Panel(
                panel_content,
                title=f"[cyan]{doc.title}[/cyan] [dim]({doc.source})[/dim]",
                subtitle=f"[dim]{doc.timestamp}[/dim]",
            )
        )


@memory_app.command("recent")
def memory_recent(
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Show recently ingested items."""
    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    results = asyncio.run(store.get_recent(limit=limit))

    if not results:
        console.print("[yellow]No documents stored yet.[/yellow]")
        return

    table = Table(title="Recent Documents")
    table.add_column("Title", style="cyan")
    table.add_column("Source")
    table.add_column("Type")
    table.add_column("Timestamp", style="dim")

    for doc in results:
        table.add_row(doc.title[:60], doc.source, doc.content_type, str(doc.timestamp))

    console.print(table)


@memory_app.command("purge")
def memory_purge(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Purge only this source"),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation"),
) -> None:
    """Clear stored memory."""
    if not confirm:
        msg = f"Purge all data from {source}?" if source else "Purge ALL stored data?"
        if not typer.confirm(msg):
            raise typer.Abort()

    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    asyncio.run(store.purge(source=source))
    console.print("[green]Memory purged.[/green]")


# --- Context commands ---

context_app = typer.Typer(help="Manage generated context files")
app.add_typer(context_app, name="context")


@context_app.command("generate")
def context_generate() -> None:
    """Force regenerate all context .md files."""
    console.print("[cyan]Generating context files...[/cyan]")
    console.print("[yellow]Not yet implemented (Phase 4)[/yellow]")


@context_app.command("show")
def context_show() -> None:
    """List generated context files."""
    config = MneiaConfig.load()
    output_dir = Path(config.context_output_dir)
    if not output_dir.exists():
        console.print("[yellow]No context files generated yet.[/yellow]")
        return

    table = Table(title="Context Files")
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Modified", style="dim")

    for f in sorted(output_dir.glob("*.md")):
        stat = f.stat()
        size = f"{stat.st_size:,} bytes"
        from datetime import datetime

        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(f.name, size, modified)

    console.print(table)


@context_app.command("link")
def context_link(target_dir: str) -> None:
    """Symlink context files to a project directory."""
    config = MneiaConfig.load()
    source = Path(config.context_output_dir)
    target = Path(target_dir)

    if not source.exists():
        console.print("[red]No context files generated yet. Run mneia context generate first.[/red]")
        raise typer.Exit(1)

    target.mkdir(parents=True, exist_ok=True)
    for f in source.glob("*.md"):
        link = target / f.name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(f)
        console.print(f"[green]Linked {f.name} -> {target}[/green]")


# --- Ask command ---


@app.command()
def ask(
    question: str,
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Limit to source"),
) -> None:
    """Ask a question about your knowledge."""
    console.print("[yellow]Not yet implemented (Phase 7)[/yellow]")


# --- Graph commands ---

graph_app = typer.Typer(help="Explore your knowledge graph")
app.add_typer(graph_app, name="graph")


@graph_app.command("show")
def graph_show() -> None:
    """Show knowledge graph summary."""
    console.print("[yellow]Not yet implemented (Phase 3)[/yellow]")


@graph_app.command("entities")
def graph_entities(
    entity_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
) -> None:
    """List entities in the knowledge graph."""
    console.print("[yellow]Not yet implemented (Phase 3)[/yellow]")


# --- Marketplace commands ---

marketplace_app = typer.Typer(help="Browse and install connectors")
app.add_typer(marketplace_app, name="marketplace")


@marketplace_app.command("search")
def marketplace_search(query: str) -> None:
    """Search available connectors in the marketplace."""
    console.print("[yellow]Not yet implemented (Phase 9)[/yellow]")


@marketplace_app.command("install")
def marketplace_install(name: str) -> None:
    """Install a connector from the marketplace."""
    console.print("[yellow]Not yet implemented (Phase 9)[/yellow]")


@marketplace_app.command("list")
def marketplace_list_cmd() -> None:
    """List all available marketplace connectors."""
    console.print("[yellow]Not yet implemented (Phase 9)[/yellow]")


# --- Logs & Update ---


@app.command()
def logs(
    level: str = typer.Option("info", "--level", "-l", help="Log level filter"),
) -> None:
    """Tail daemon logs."""
    console.print("[yellow]Not yet implemented (Phase 5)[/yellow]")


@app.command()
def update() -> None:
    """Check for updates and install if available."""
    import httpx

    console.print("[cyan]Checking for updates...[/cyan]")
    try:
        resp = httpx.get(
            "https://api.github.com/repos/riverphoenix/mneia/releases/latest",
            timeout=5,
        )
        if resp.status_code == 200:
            latest = resp.json()["tag_name"].lstrip("v")
            if latest != __version__:
                console.print(f"[green]New version available: {latest} (current: {__version__})[/green]")
                console.print("Run: [cyan]pipx upgrade mneia[/cyan]")
            else:
                console.print(f"[green]You're on the latest version ({__version__})[/green]")
        else:
            console.print("[yellow]Could not check for updates.[/yellow]")
    except Exception:
        console.print("[yellow]Could not reach GitHub. Check your connection.[/yellow]")
